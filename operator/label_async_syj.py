import os
import re
import json
import random
import asyncio
import aiofiles
import os.path as osp
from tqdm.asyncio import tqdm_asyncio
from tqdm import tqdm
from openai import AsyncOpenAI


# ====== 全局配置 ======
MAX_CONCURRENT = 8          # 同时处理的文件数（防止内存占用太大）
REQUESTS_PER_SECOND = 4     # API QPS 限制（按模型速率调整）

# 全局信号量与限流控制
semaphore = asyncio.Semaphore(MAX_CONCURRENT)
rate_limiter = asyncio.Semaphore(REQUESTS_PER_SECOND)

# ====== 初始化异步客户端 ======
# client = AsyncOpenAI(
#         api_key="bce-v3/ALTAK-oHUU6tqXfePF1XUIGEKLn/7785fd99676c59851f15fdd71a1c2b5f914964ce", 
#         base_url="https://qianfan.baidubce.com/v2",
#         timeout=5 * 3600  
#     )

api_key = api_key or os.getenv("DASHSCOPE_API_KEY")
base_url = base_url or "https://dashscope.aliyuncs.com/compatible-mode/v1"
client = OpenAI(api_key=self.api_key, base_url=self.base_url)

# ====== API 调用函数（限流封装）======
async def rate_limited_completion(prompt: str):
    """全局限流的异步模型调用"""
    async with rate_limiter:
        try:
            completion = await client.chat.completions.create(
                model="deepseek-v3",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=16384,
            )
            await asyncio.sleep(1 / REQUESTS_PER_SECOND)  # 控制速率

            result = completion.choices[0].message.content
            start_index = result.find("{")
            end_index = result.rfind("}")
            if start_index != -1 and end_index != -1 and start_index < end_index:
                result = result[start_index:end_index + 1]
            return json.loads(result)
        except Exception as e:
            print(f"API 调用异常：{e}", flush=True)
            return {"keyword": []}
        
def get_prompt(text):
    prompt = '''
    你是一个资料分析专家，请对我给你的一组问答信息进行关键词提取。要求如下：
    1. 你需要阅读给出的问答信息，并凝练提取3个最相关且恰当的关键词。
    2. 返回格式如下，严格按照格式输出，除此之外不要增加任何多余字符：
    {"keyword": ["关键词1", ...]}
    3. 需要分类的信息如下：
    ''' 
    
    prompt = prompt + text
    return prompt

def split_list(data, ratio=0.9, seed=None):
    """
    按约9:1随机划分列表为两个部分。
    :param data: 原始列表
    :param ratio: 划分比例（默认0.9）
    :param seed: 随机种子（可选）
    :return: (list_a, list_b)
    """
    if seed is not None:
        random.seed(seed)
    
    n = len(data)
    
    # 边界情况处理
    if n == 0:
        return [], []
    if n == 1:
        return [data[0]], []
    
    # 计算划分数量
    n_a = int(n * ratio)
    
    # 如果总数小于10，则强制两个非空
    if n < 10:
        n_a = max(1, n - 1)
    
    # 随机采样
    indices = list(range(n))
    random.shuffle(indices)
    idx_a = set(indices[:n_a])
    
    list_a = [data[i] for i in range(n) if i in idx_a]
    list_b = [data[i] for i in range(n) if i not in idx_a]
    
    return list_a, list_b

# ====== 核心处理函数 ======
async def process_file(fpath, labels, dir_path, output_dir):
    """处理单个文件（异步版）"""
    async with semaphore:
        if osp.exists(osp.join(osp.splitext(osp.join(output_dir, osp.relpath(fpath, dir_path)))[0], f"{osp.splitext(osp.basename(fpath))[0]}_train.json")): return
        match = re.match(r'^(\d+)', osp.basename(fpath).strip())
        if not match:
            print(f"文件名不合法：{fpath}", flush=True)
            return
        fid = match.group(1)

        try:
            tag = labels[fid]

            # === 异步读取文件 ===
            async with aiofiles.open(fpath, "r", encoding="utf-8") as f:
                contents = json.loads(await f.read())

            # === 逐条处理 ===
            results = []
            for qa in contents:
                qa["原文件"] = qa["file_name"] + ".pdf" 
                qa["洗料文件"] = qa["file_name"] + ".md"
                qa.pop("file_path")
                qa.pop("file_name")
                qa.pop("block_index")
                qa.pop("judge")
                qa.update(tag)

                text = f"Question: {qa['Q']}\nAnswer: {qa['A']}\n"
                prompt = get_prompt(text)

                try:
                    label = await rate_limited_completion(prompt)
                    qa["keyword"] = label.get("keyword", [])
                except Exception as e:
                    print(f"QA出错跳过: {e}\n{fpath}: {qa['Q']}", flush=True)
                    qa["keyword"] = []  # 出错也填空，保持数据结构完整
                if qa["keyword"]:
                    results.append(qa)

            # === 数据划分并保存 ===
            train, test = split_list(results)
            output_file_dir = osp.splitext(
                osp.join(output_dir, osp.relpath(fpath, dir_path))
            )[0]
            os.makedirs(output_file_dir, exist_ok=True)

            base = osp.splitext(osp.basename(fpath))[0]

            if train:
                async with aiofiles.open(
                    osp.join(output_file_dir, f"{base}_train.json"), "w", encoding="utf-8"
                ) as f:
                    await f.write(json.dumps(train, ensure_ascii=False, indent=4))

            if test:
                async with aiofiles.open(
                    osp.join(output_file_dir, f"{base}_test.json"), "w", encoding="utf-8"
                ) as f:
                    await f.write(json.dumps(test, ensure_ascii=False, indent=4))

        except Exception as e:
            print(f"{fpath} 处理失败：{e}", flush=True)


# ====== 主入口函数 ======
# async def main(files, labels, dir_path, output_dir):
#     tasks = []
#     for fpath in files:
#         await semaphore.acquire()
#         task = asyncio.create_task(process_file(fpath, labels, dir_path, output_dir))
#         task.add_done_callback(lambda t: semaphore.release())
#         tasks.append(task)

#     for _ in tqdm_asyncio.as_completed(tasks, desc="Processing"):
#         await _

async def main(files, labels, dir_path, output_dir):
    tasks = [asyncio.create_task(process_file(fpath, labels, dir_path, output_dir)) for fpath in files]

    pbar = tqdm(total=len(tasks), desc="Processing")
    for task in asyncio.as_completed(tasks):
        await task
        pbar.update(1)
    pbar.close()



if __name__ == "__main__":
    # 假设这些变量已定义
    with open("/mnt/data/guizi/sunyijie/市政处0105-84/【市政处】.json", "r", encoding="utf-8") as f:
        labels = json.load(f)

    dir_path = "/mnt/data/guizi/sunyijie/市政处0105-84/tmp/common"
    output_dir = "/mnt/data/guizi/sunyijie/市政处0105-84/qa"
    os.makedirs(output_dir, exist_ok=True)

    files = []
    for root, dnames, fnames in os.walk(dir_path):
        for fname in fnames:
            if fname.endswith(".json"):
                files.append(osp.join(root, fname))
    # files = ['/mnt/data/guizi/1021-补-json/13848-03《其他样本社区 》排版+.json', '/mnt/data/guizi/1021-补-json/16584-全国国土空间规划实施监测网络建设工作方案（2023-2027年）.json']
    asyncio.run(main(files, labels, dir_path, output_dir))
