import bcrypt

# 1. 암호화하고 싶은 비밀번호 (로그인할 때 쓸 비밀번호)
password_to_hash = b"123"

# 2. 비밀번호를 bcrypt로 암호화하기
hashed_password = bcrypt.hashpw(password_to_hash, bcrypt.gensalt())

# 3. 암호화된 결과를 화면에 출력하기
print("아래 값을 복사해서 MongoDB에 붙여넣으세요:")
print(hashed_password)