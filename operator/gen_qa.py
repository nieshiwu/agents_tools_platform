import os
import sys
import json
import re
import pandas as pd
from docx import Document
from openai import OpenAI
from openai import AsyncOpenAI
from pathlib import Path
import time
from datetime import datetime
import asyncio
from tqdm.asyncio import tqdm_asyncio

class DocExtractor:
    def __init__(self, doc_path):
        self.doc_path = doc_path
        self.doc = Document(doc_path)
        self.pattern = r"[，。！？；：“”‘’（）()【】《》,.!?;:\"'’“”\-]"

    def extract(self, output_file=None):
        output = []
        field = None
        for p in self.doc.paragraphs:
            if p.style.name == "Heading 1":
                continue
            if p._p.pPr is not None and p._p.pPr.numPr is not None:
                keyword = p.text.strip()
                keyword = re.sub(self.pattern, '', keyword.lower()).strip()
                if len(output) > 0:
                    latest_answer = output[-1]['answer'][:-1]
                    if latest_answer and latest_answer[-1] != '。':
                        latest_answer += '。'
                    latest_keyword = output[-1]['keyword'][0]
                    if not latest_answer.startswith(latest_keyword) and not latest_answer.startswith("同"):
                        output[-1]['answer'] = f"{latest_keyword}是指{latest_answer}"
                    if not latest_answer.startswith(latest_keyword) and latest_answer.startswith("同"):
                        output[-1]['answer'] = f"{latest_keyword}，{latest_answer}"
                questions = [
                    f"什么是{keyword}",
                    f"{keyword}是什么",
                    f"{keyword}的定义是什么",
                    f"介绍一下{keyword}",
                    f"说明一下{keyword}",
                    f"解释一下{keyword}",
                    f"描述一下{keyword}",
                    f"{keyword}的本质是什么",
                    f"{keyword}的基本概念是什么",
                    f"{keyword}的主要特征有哪些",
                    f"{keyword}的核心价值是什么",
                    f"{keyword}的核心理念是什么",
                    f"{keyword}的功能是什么",
                    f"{keyword}的作用是什么",
                    f"{keyword}的目的是什么"
                ]
                output.append({"keyword": [keyword], "source": [], "questions": questions, "answer": ""})
                field = None
            else:
                if p.text.startswith("定义"):
                    answer = p.text.lstrip("定义：")
                    if len(answer.strip()) > 0 and len(output) > 0:
                        output[-1]['answer'] += (answer + '\n')
                    field = "define"
                elif p.text.startswith("来源"):
                    source = [p.text.strip().lstrip("来源：")]
                    if len(source) > 0 and len(output) > 0:
                        output[-1]['source'].extend(source)
                    field = "source"
                elif p.text.startswith("重要数据"):
                    data = p.text.lstrip("重要数据：")
                    if len(data.strip()) > 0 and len(output) > 0:
                        output[-1]['answer'] += (data + '\n')
                    field = "data"
                else:
                    text = p.text.strip()
                    if field == "define" and len(output) > 0:
                        output[-1]['answer'] += (text + '\n')
                    elif field == "source" and len(output) > 0:
                        output[-1]['source'].append(text)
                    elif field == "data" and len(output) > 0:
                        output[-1]['answer'] += (text + '\n')
                if field == None:
                    answer = p.text.strip()
                    if len(answer.strip()) > 0 and len(output) > 0:
                        output[-1]['answer'] += (answer + '\n')
                    field = "define"

        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(output, f, ensure_ascii=False, indent=4)
        return output

class ExcelExtractor:
    def __init__(self, excel_path):
        self.excel_path = excel_path
        self.df = pd.read_excel(excel_path)
        self.pattern = r"[，。！？；：“”‘’（）()【】《》,.!?;:\"'’“”\-]"

    def extract(self, output_file=None):
        df = self.df
        output = []
        for i in range(len(df.iloc[:, 1])):
            keyword = str(df.iloc[:, 1][i])
            keyword = re.sub(self.pattern, '', keyword.lower()).strip()
            if str(keyword) == 'nan':
                continue
            answer = str(df.iloc[:, 2][i])
            if not answer.endswith('。'):
                answer += '。'
            source = str(df.iloc[:, 3][i])
            keydata = str(df.iloc[:, 4][i])

            if str(keydata) != 'nan' and str(keydata) != "/":
                if not keydata.endswith('。'):
                    keydata += '。'
                answer += ('\n' + keydata)
            questions = [
                f"什么是{keyword}",
                f"{keyword}是什么",
                f"{keyword}的定义是什么",
                f"介绍一下{keyword}",
                f"说明一下{keyword}",
                f"解释一下{keyword}",
                f"描述一下{keyword}",
                f"{keyword}的本质是什么",
                f"{keyword}的基本概念是什么",
                f"{keyword}的主要特征有哪些",
                f"{keyword}的核心价值是什么",
                f"{keyword}的核心理念是什么",
                f"{keyword}的功能是什么",
                f"{keyword}的作用是什么",
                f"{keyword}的目的是什么"
            ]
            term = {
                "keyword": [keyword],
                "source": [source] if str(source) != 'nan' else [],
                "questions": questions,
                "answer": answer if answer.startswith(keyword) else f"{keyword}是指{answer}"
            }
            output.append(term)

        if output_file: 
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(output, f, ensure_ascii=False, indent=4)
        return output

class QAEnhancer:
    def __init__(self, api_key=None, base_url=None, model="qwen-plus"):
        self.api_key = api_key or os.getenv("DASHSCOPE_API_KEY")
        self.base_url = base_url or os.getenv("OPENAI_BASE_URL")
        self.r1_client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        self.model = model
        self.pattern = r"[，。！？；：“”‘’（）()【】《》,.!?;:\"'’“”\-]"

    @staticmethod
    def parse_questions(output_text):
        pattern = r"[，。！？；：“”‘’（）()【】《》,.!?;:\"'’“”\-]"
        questions = []
        try:
            parsed = json.loads(output_text)
            if isinstance(parsed, list):
                questions = [q.strip() for q in parsed if q.strip()]
                return questions
            elif isinstance(parsed, dict) and 'questions' in parsed:
                questions = [q.strip() for q in parsed['questions'] if q.strip()]
                return questions
        except:
            pass
        lines = output_text.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
            match = re.match(r'^[\d①②③④⑤⑥⑦⑧⑨⑩]+[\.、）)]\s*(.+)', line)
            if match:
                question = match.group(1).strip()
                if question:
                    question = re.sub(pattern, '', question).strip()
                    questions.append(question)
            elif re.match(r'^[-*]\s*(.+)', line):
                question = re.match(r'^[-*]\s*(.+)', line).group(1).strip()
                if question:
                    question = re.sub(pattern, '', question).strip()
                    questions.append(question)
            elif '？' in line or '?' in line or len(line) > 10:
                line = re.sub(pattern, '', line).strip()   
                questions.append(line)
        return questions

    def enhance(self, input_dict, output_file=None, re_generate=None):
        re_generate = re_generate or []
        results = []
        for item in input_dict:
            keywords = item['keyword']
            answer = item['answer']
            source = item.get('source', [])
            all_questions = item.get('questions', [])
            for keyword in keywords:
                if keyword in re_generate or len(re_generate) == 0:
                    num = (len(answer) // 10 + 1) * 2
                    message = f'''{answer}\n这是'{keyword}'的介绍。 帮我针对介绍，生成{num}个左右询问'{keyword}'的问题，且这些问题都必须只能从介绍中回答。\n每个问题都要包含{keyword}这个字段。要求，问题语义通畅，逻辑合理。\n输出格式为:\n1. 问题1\n2. 问题2\n3. 问题3\n4. 问题4\n'''
                    completion = self.r1_client.chat.completions.create(
                        model=self.model,
                        messages=[
                            {"role": "system", "content": "You are a helpful assistant."},
                            {"role": "user", "content": message},
                        ],
                        extra_body={"enable_thinking": False},
                    )
                    output = completion.choices[0].message.content
                    questions = self.parse_questions(output)
                    all_questions.extend(questions)
                    print(f"处理完成: {keyword}, 生成 {len(questions)} 个问题")
            result_item = {
                "keyword": keywords,
                "source": source,
                "questions": all_questions,
                "answer": answer
            }
            results.append(result_item)
        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=4)
            print(f"\n结果已保存到 {output_file}，共 {len(results)} 条记录")
        return results

class QAChecker:
    def __init__(self, api_key=None, base_url=None, model="qwen3-max"):
        self.api_key = api_key or os.getenv("DASHSCOPE_API_KEY")
        self.base_url = base_url or "https://dashscope.aliyuncs.com/compatible-mode/v1"
        self.r1_client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        self.model = model

    def check(self, input_dict, output_file=None):
        for item in input_dict:
            keywords = item['keyword']
            answer = item['answer']
            source = item.get('source', [])
            all_questions = item.get('questions', [])
            questions_to_check = list(all_questions)
            for question in questions_to_check:
                message = f'''问题是："{question}"
参考答案是："{answer}"
问题可以用参考答案来回答吗？
如果可以，只回复”true“，如果不可以，只回复”false“
                '''
                completion = self.r1_client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "user", "content": message},
                    ],
                    extra_body={"enable_thinking": False},
                )
                output = completion.choices[0].message.content
                if output.strip() == "false":
                    print(f"问题：{question} 不能用参考答案来回答")
                    item['questions'].remove(question)
        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(input_dict, f, ensure_ascii=False, indent=4)
            print(f"\n结果已保存到 {output_file}，共 {len(input_dict)} 条记录")
        return input_dict

class QAEnhancerAsync:
    def __init__(self, api_key=None, base_url=None, model="qwen-plus"):
        self.api_key = api_key or os.getenv("DASHSCOPE_API_KEY")
        self.base_url = base_url or "https://dashscope.aliyuncs.com/compatible-mode/v1"
        self.r1_client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
        self.model = model
        self.pattern = r"[，。！？；：“”‘’（）()【】《》,.!?;:\"'’“”-]"

    @staticmethod
    def parse_questions(output_text):
        pattern = r"[，。！？；：“”‘’（）()【】《》,.!?;:\"'’“”-]"
        questions = []
        try:
            parsed = json.loads(output_text)
            if isinstance(parsed, list):
                questions = [q.strip() for q in parsed if q.strip()]
                return questions
            elif isinstance(parsed, dict) and 'questions' in parsed:
                questions = [q.strip() for q in parsed['questions'] if q.strip()]
                return questions
        except:
            pass
        lines = output_text.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
            match = re.match(r'^[\d①②③④⑤⑥⑦⑧⑨⑩]+[\.,、）)]\s*(.+)', line)
            if match:
                question = match.group(1).strip()
                if question:
                    question = re.sub(pattern, '', question).strip()
                    questions.append(question)
            elif re.match(r'^[-*]\s*(.+)', line):
                question = re.match(r'^[-*]\s*(.+)', line).group(1).strip()
                if question:
                    question = re.sub(pattern, '', question).strip()
                    questions.append(question)
            elif '？' in line or '?' in line or len(line) > 10:
                line = re.sub(pattern, '', line).strip()   
                questions.append(line)
        return questions

    async def enhance(self, input_dict, output_file=None, re_generate=None):
        re_generate = re_generate or []
        results = []
        async def process_item(item):
            keywords = item['keyword']
            answer = item['answer']
            source = item.get('source', [])
            all_questions = item.get('questions', [])
            for keyword in keywords:
                if keyword in re_generate or len(re_generate) == 0:
                    num = (len(answer) // 10 + 1) * 2
                    message = f'''{answer}\n这是'{keyword}'的介绍。 帮我针对介绍，生成{num}个左右询问'{keyword}'的问题，且这些问题都必须只能从介绍中回答。\n每个问题都要包含{keyword}这个字段。要求，问题语义通畅，逻辑合理。\n输出格式为:\n1. 问题1\n2. 问题2\n3. 问题3\n4. 问题4\n'''
                    completion = await self.r1_client.chat.completions.create(
                        model=self.model,
                        messages=[
                            {"role": "system", "content": "You are a helpful assistant."},
                            {"role": "user", "content": message},
                        ],
                        extra_body={"enable_thinking": False},
                    )
                    output = completion.choices[0].message.content
                    questions = self.parse_questions(output)
                    all_questions.extend(questions)
            return {
                "keyword": keywords,
                "source": source,
                "questions": all_questions,
                "answer": answer
            }
        tasks = [process_item(item) for item in input_dict]
        results = await tqdm_asyncio.gather(*tasks)
        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=4)
        return results

class QACheckerAsync:
    def __init__(self, api_key=None, base_url=None, model="qwen3-max"):
        self.api_key = api_key or os.getenv("DASHSCOPE_API_KEY")
        self.base_url = base_url or "https://dashscope.aliyuncs.com/compatible-mode/v1"
        self.r1_client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
        self.model = model

    async def check(self, input_dict, output_file=None):
        async def process_question(item, question):
            answer = item['answer']
            message = f'''问题是："{question}"
参考答案是："{answer}"
问题可以用参考答案来回答吗？
如果可以，只回复”true“，如果不可以，只回复”false“
            '''
            completion = await self.r1_client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "user", "content": message},
                ],
                extra_body={"enable_thinking": False},
            )
            output = completion.choices[0].message.content
            return output.strip() == "true"

        for item in input_dict:
            questions_to_check = list(item['questions'])
            tasks = [process_question(item, q) for q in questions_to_check]
            results = await tqdm_asyncio.gather(*tasks)
            item['questions'] = [q for q, keep in zip(questions_to_check, results) if keep]
        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(input_dict, f, ensure_ascii=False, indent=4)
        return input_dict

class QABatchGenerator:
    def __init__(self, api_key=None, base_url=None, model="qwen-plus"):
        self.api_key = api_key or os.getenv("DASHSCOPE_API_KEY")
        self.base_url = base_url or "https://dashscope.aliyuncs.com/compatible-mode/v1"
        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        self.model = model

    @staticmethod
    def parse_questions(output_text):
        questions = []
        try:
            parsed = json.loads(output_text)
            if isinstance(parsed, list):
                questions = [q.strip() for q in parsed if q.strip()]
                return questions
            elif isinstance(parsed, dict) and 'questions' in parsed:
                questions = [q.strip() for q in parsed['questions'] if q.strip()]
                return questions
        except:
            pass
        lines = output_text.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
            match = re.match(r'^[\d①②③④⑤⑥⑦⑧⑨⑩]+[\.、）)]\s*(.+)', line)
            if match:
                question = match.group(1).strip()
                if question:
                    questions.append(question)
            elif re.match(r'^[-*]\s*(.+)', line):
                question = re.match(r'^[-*]\s*(.+)', line).group(1).strip()
                if question:
                    questions.append(question)
            elif '？' in line or '?' in line or len(line) > 10:
                questions.append(line)
        return questions

    def generate_batch_qa(self, input_dict, output_file=None, re_generate=None):
        re_generate = re_generate or []
        batch_list = []
        for index, item in enumerate(input_dict):
            keywords = item['keyword']
            answer = item['answer']
            source = item.get('source', [])
            all_questions = item.get('questions', [])
            for keyword in keywords:
                if keyword in re_generate or len(re_generate) == 0:
                    num = (len(answer) // 10 + 1) * 2
                    message = f'''{answer}\n这是'{keyword}'的介绍。 帮我针对介绍，生成{num}个左右询问'{keyword}'的问题，且这些问题都必须只能从介绍中回答。\n每个问题都要包含{keyword}这个字段。要求，问题语义通畅，逻辑合理。\n输出格式为:\n1. 问题1\n2. 问题2\n3. 问题3\n4. 问题4\n'''
                    batch_format = {
                        "custom_id": f"{index}",
                        "method": "POST",
                        "url": "/v1/chat/completions",
                        "body": {
                            "model": self.model,
                            "messages": [
                                {"role": "user", "content": message}
                            ],
                            "extra_body": {"enable_thinking": False}
                        }
                    }
                    batch_list.append(batch_format)
        ts_ms = int(datetime.now().timestamp() * 1000)
        tmp_batch_file = f"/tmp/batch_{ts_ms}.jsonl"
        with open(tmp_batch_file, 'w', encoding='utf-8') as f:
            for item in batch_list:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
        print(f"正在上传包含请求信息的JSONL文件...")
        file_object = self.client.files.create(file=Path(tmp_batch_file), purpose="batch")
        print(f"文件上传成功。得到文件ID: {file_object.id}\n")
        print(f"正在基于文件ID，创建Batch任务...")
        batch = self.client.batches.create(input_file_id=file_object.id, endpoint="/v1/chat/completions", completion_window="24h")
        print(f"Batch任务创建完成。 得到Batch任务ID: {batch.id}\n")
        batch_id = batch.id
        status = ""
        while status not in ["completed", "failed", "expired", "cancelled"]:
            batch = self.client.batches.retrieve(batch_id=batch_id)
            status = batch.status
            print(f"Batch任务状态: {status}\n等待任务完成...")
            time.sleep(10)
        if status == "failed":
            print(f"Batch任务失败。错误信息为:{batch.errors}\n")
        output_file_id = batch.output_file_id
        results = []
        if output_file_id:
            content = self.client.files.content(output_file_id)
            resp_text = content.response.text
            data_list = []
            for line in resp_text.splitlines():
                if line.strip():
                    data_list.append(json.loads(line))
            for resp_item in data_list:
                output = resp_item['response']['body']['choices'][0]['message']['content']
                index = int(resp_item['custom_id'])
                item = input_dict[index]
                keywords = item['keyword']
                answer = item['answer']
                source = item.get('source', [])
                all_questions = item.get('questions', [])
                questions = self.parse_questions(output)
                all_questions.extend(questions)
                print(f"处理完成: {keywords}, 生成 {len(questions)} 个问题")
                result_item = {
                    "keyword": keywords,
                    "source": source,
                    "questions": all_questions,
                    "answer": answer
                }
                results.append(result_item)

        os.remove(tmp_batch_file)
        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=4)
            print(f"\n结果已保存到 {output_file}，共 {len(results)} 条记录")
        return results

class QABatchChecker:
    def __init__(self, api_key=None, base_url=None, model="qwen-plus"):
        self.api_key = api_key or os.getenv("DASHSCOPE_API_KEY")
        self.base_url = base_url or "https://dashscope.aliyuncs.com/compatible-mode/v1"
        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        self.model = model

    def batch_check(self, input_dict, output_file=None):
        batch_list = []
        for index0, item in enumerate(input_dict):
            keywords = item['keyword']
            answer = item['answer']
            source = item.get('source', [])
            all_questions = item.get('questions', [])
            for index1, question in enumerate(all_questions):
                message = f'''问题是："{question}"
参考答案是："{answer}"
问题可以用参考答案来回答吗？
如果可以，只回复”true“，如果不可以，只回复”false“
                '''
                batch_format = {
                    "custom_id": f"{index0}_{index1}",
                    "method": "POST",
                    "url": "/v1/chat/completions",
                    "body": {
                        "model": self.model,
                        "messages": [
                            {"role": "user", "content": message}
                        ],
                        "extra_body": {"enable_thinking": False}
                    }
                }
                batch_list.append(batch_format)
        ts_ms = int(datetime.now().timestamp() * 1000)
        tmp_batch_file = f"/tmp/batch_check_{ts_ms}.jsonl"
        with open(tmp_batch_file, 'w', encoding='utf-8') as f:
            for item in batch_list:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
        print(f"正在上传包含请求信息的JSONL文件...")
        file_object = self.client.files.create(file=Path(tmp_batch_file), purpose="batch")
        print(f"文件上传成功。得到文件ID: {file_object.id}\n")
        print(f"正在基于文件ID，创建Batch任务...")
        batch = self.client.batches.create(input_file_id=file_object.id, endpoint="/v1/chat/completions", completion_window="24h")
        print(f"Batch任务创建完成。 得到Batch任务ID: {batch.id}\n")
        batch_id = batch.id
        status = ""
        start_time = time.time()
        while status not in ["completed", "failed", "expired", "cancelled"]:
            batch = self.client.batches.retrieve(batch_id=batch_id)
            status = batch.status
            print(f"Batch任务状态: {status}\n等待任务完成...")
            time.sleep(3)
        end_time = time.time()
        print(f"Batch任务完成，状态: {status}，总耗时: {end_time - start_time:.2f} 秒\n")
        if status == "failed":
            print(f"Batch任务失败。错误信息为:{batch.errors}\n")
        remove_dict = {}
        output_file_id = batch.output_file_id
        if output_file_id:
            content = self.client.files.content(output_file_id)
            resp_text = content.response.text
            data_list = []
            for line in resp_text.splitlines():
                if line.strip():
                    data_list.append(json.loads(line))
            for resp_item in data_list:
                output = resp_item['response']['body']['choices'][0]['message']['content']
                if output.strip() == "false":
                    index0 = int(resp_item['custom_id'].split('_')[0])
                    index1 = int(resp_item['custom_id'].split('_')[1])
                    print(f"问题：{input_dict[index0]['questions'][index1]} 不能用参考答案来回答")
                    if remove_dict.__contains__(index0):
                        remove_dict[index0].append(index1)
                    else:
                        remove_dict[index0] = [index1]
        print(">>> remove_dict =", remove_dict)
        for index0, index1_list in remove_dict.items():
            for index1 in sorted(index1_list, reverse=True):
                item = input_dict[index0]
                item['questions'].pop(index1)
        os.remove(tmp_batch_file)
        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(input_dict, f, ensure_ascii=False, indent=4)
            print(f"\n结果已保存到 {output_file}，共 {len(input_dict)} 条记录")
        return input_dict

def main():
    # if len(sys.argv) < 4:
    #     print("Usage: python pipeline_qa.py <mode> <input_file> <output_file> [re_generate_keywords]")
    #     return
    # mode = sys.argv[1]
    # input_file = sys.argv[2]
    # output_file = sys.argv[3]

    mode = 'qa'            # 'doc', 'excel', 'qa', 'check', 'qa_async', 'check_async', 'batch_qa', 'batch_check'
    input_file = r'D:\workspace\tools_platform\file\output.json'   # or 'data/terms.docx' or 'data/terms.json'

    output_file = 'D:\\workspace\\tools_platform\\file\\output_encha.json'  # Output file path

    if mode == 'doc':
        DocExtractor(input_file).extract(output_file)
    elif mode == 'excel':
        ExcelExtractor(input_file).extract(output_file)
    elif mode == 'qa':
        re_generate = sys.argv[4].split(',') if len(sys.argv) > 4 else []
        if input_file.endswith('.json'):
            with open(input_file, 'r', encoding='utf-8') as f:
                input_dict = json.load(f)
        else:
            input_dict = input_file
        QAEnhancer().enhance(input_dict, output_file, re_generate)
    elif mode == 'check':
        if input_file.endswith('.json'):
            with open(input_file, 'r', encoding='utf-8') as f:
                input_dict = json.load(f)
        else:
            input_dict = input_file
        QAChecker().check(input_dict, output_file)
    elif mode == 'qa_async':
        re_generate = sys.argv[4].split(',') if len(sys.argv) > 4 else []
        if input_file.endswith('.json'):
            with open(input_file, 'r', encoding='utf-8') as f:
                input_dict = json.load(f)
        else:
            input_dict = input_file
        asyncio.run(QAEnhancerAsync("EMPTY", "http://localhost:8800/v1", "qwen").enhance(input_dict, output_file, re_generate))
    elif mode == 'check_async':
        if input_file.endswith('.json'):
            with open(input_file, 'r', encoding='utf-8') as f:
                input_dict = json.load(f)
        else:
            input_dict = input_file
        asyncio.run(QACheckerAsync("EMPTY", "http://localhost:8800/v1", "qwen").check(input_dict, output_file))
    elif mode == 'batch_qa':
        re_generate = sys.argv[4].split(',') if len(sys.argv) > 4 else []
        if input_file.endswith('.json'):
            with open(input_file, 'r', encoding='utf-8') as f:
                input_dict = json.load(f)
        else:
            input_dict = input_file
        QABatchGenerator().generate_batch_qa(input_dict, output_file, re_generate)
    elif mode == 'batch_check':
        if input_file.endswith('.json'):
            with open(input_file, 'r', encoding='utf-8') as f:
                input_dict = json.load(f)
        else:
            input_dict = input_file
        QABatchChecker().batch_check(input_dict, output_file)
    else:
        print("Unknown mode. Use 'doc', 'excel', 'qa', 'check', 'qa_async', 'check_async', 'batch_qa', or 'batch_check'.")

if __name__ == "__main__":
    main()

