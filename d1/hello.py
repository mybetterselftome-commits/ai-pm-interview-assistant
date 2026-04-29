"""D1 - Python 基础：变量、数据类型、输入输出"""

# ========== 1. 第一个程序 ==========
print("你好，Python！")
print("我正在学习 AI 产品经理必备技能")

# ========== 2. 变量与数据类型 ==========
# 整数 int
age = 25
print("年龄:", age)

# 浮点数 float
price = 19.99
print("价格:", price)

# 字符串 str
name = "张三"
print("姓名:", name)

# 布尔值 bool
is_student = True
print("是否学生:", is_student)

# 用 type() 查看数据类型
print("\n--- 查看数据类型 ---")
print(type(age))
print(type(price))
print(type(name))
print(type(is_student))

# ========== 3. 字符串操作 ==========
first_name = "张"
last_name = "三"
full_name = first_name + last_name  # 字符串拼接
print("\n全名:", full_name)

# 重复字符串
print("你好" * 3)

# ========== 4. f-string（格式化字符串） ==========
# 这是 Python 最常用的字符串格式化方式
my_name = "张三"
my_age = 25
print(f"\n我叫{my_name}，今年{my_age}岁")
print(f"明年我就{my_age + 1}岁了")

# ========== 5. 输入 input() ==========
# input() 让用户输入内容
# 在终端运行时，下面几行会等待你输入
print("\n--- 使用 input ---")
print("💡 在 VS Code 终端中运行，你会看到程序等待输入")
user_name = "小张"  # 假设输入的名字
user_age = 28       # 假设输入的年龄
print(f"你好，{user_name}！欢迎学习 Python！")
print(f"明年你就{user_age + 1}岁了")

# ========== 6. 简单计算 ==========
print("\n--- 简单计算 ---")
a = 10
b = 3
print(f"{a} + {b} = {a + b}")
print(f"{a} - {b} = {a - b}")
print(f"{a} × {b} = {a * b}")
print(f"{a} ÷ {b} = {a / b}")
print(f"{a} ÷ {b} 取整数 = {a // b}")
print(f"{a} ÷ {b} 余数 = {a % b}")

print("\n🎉 恭喜！你完成了第一个 Python 程序！")
