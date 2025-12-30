import psycopg2  # 需先安装：pip install psycopg2-binary

try:
    # 用你的 DATABASE_URL 连接
    conn = psycopg2.connect("postgresql://postgres:123456@localhost:5432/tools_platform")
    print("✅ 数据库连接成功！")
    conn.close()
except Exception as e:
    print(f"❌ 连接失败：{e}")