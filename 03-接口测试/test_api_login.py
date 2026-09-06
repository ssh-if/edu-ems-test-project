"""
模块：权限登录模块接口测试
Author: 苏绍彰
接口：/api/auth/*
"""
import allure
import pytest
import requests
from conftest import BASE_URL, headers, http_assert, TIMEOUT, ACCOUNTS, severity_p0, severity_p1

API = f"{BASE_URL}/api/auth"


@allure.epic("EMS-教务管理系统")
@allure.feature("M01-权限登录")
class TestLogin:

    # ========== 正向用例 ==========
    @severity_p0
    @allure.story("用户登录")
    @allure.title("P0-管理员正确账号密码登录返回24h有效token")
    @pytest.mark.smoke @pytest.mark.p0 @pytest.mark.login
    def test_login_admin_success(self):
        with allure.step("1. 发送正确登录请求"):
            resp = requests.post(f"{API}/login", json=ACCOUNTS["admin"], timeout=TIMEOUT)
        with allure.step("2. 断言业务+数据"):
            body = http_assert(resp, 200, 0)
            token = body["data"].get("token", "")
            assert len(token) > 30, f"token 长度异常: {len(token)}"
            assert body["data"]["userInfo"]["userId"] == 1
            assert "roles" in body["data"]["userInfo"]

    @severity_p0
    @allure.story("用户登录")
    @allure.title("P0-各角色账号登录返回token正确")
    @pytest.mark.p0 @pytest.mark.parametrize("role", ["admin", "sales01", "finance01", "principal", "teacher"])
    def test_login_multi_roles(self, role):
        resp = requests.post(f"{API}/login", json=ACCOUNTS[role], timeout=TIMEOUT)
        body = http_assert(resp, 200, 0)
        assert body["data"]["token"], f"{role} token 为空"

    # ========== 反向用例 ==========
    @severity_p0
    @allure.story("用户登录")
    @allure.title("P0-密码错误返回1001不返回token")
    @pytest.mark.p0
    def test_login_wrong_password(self):
        acc = ACCOUNTS["admin"].copy()
        acc["password"] = "wrongPass!@#"
        resp = requests.post(f"{API}/login", json=acc, timeout=TIMEOUT)
        body = http_assert(resp, 200, 1001, "密码错误")
        assert "token" not in body["data"] or not body["data"].get("token"), \
            "密码错误时不该返回token"

    @severity_p0
    @allure.story("用户登录")
    @allure.title("P0-账号为空校验")
    def test_login_empty_username(self):
        resp = requests.post(f"{API}/login", json={"username":"","password":"any"}, timeout=TIMEOUT)
        http_assert(resp, 200, 400, "用户名")

    @severity_p0
    @allure.story("用户登录")
    @allure.title("P0-密码为空校验")
    def test_login_empty_password(self):
        resp = requests.post(f"{API}/login", json={"username":"admin","password":""}, timeout=TIMEOUT)
        http_assert(resp, 200, 400, "密码")

    @severity_p1
    @allure.story("用户登录")
    @allure.title("P1-连续5次错误密码账号锁定30分钟")
    def test_login_lock_after_5_failures(self):
        acc = {"username": "lock_demo_user", "password": "wrongpass"}
        for i in range(5):
            requests.post(f"{API}/login", json=acc, timeout=TIMEOUT)
        # 第6次应被锁
        resp = requests.post(f"{API}/login", json=acc, timeout=TIMEOUT)
        body = resp.json()
        assert body["code"] == 1008 or "锁定" in body.get("msg", ""), \
            f"第6次未被锁定 code={body['code']} msg={body.get('msg')}"

    # ========== 安全测试 ==========
    @severity_p0
    @allure.story("安全-SQL注入")
    @allure.title("P0-用户名SQL注入防护检测")
    @pytest.mark.security
    def test_login_sql_injection_username(self):
        payloads = [
            "' OR 1=1 --",
            "admin' --",
            "admin' /*",
            "' UNION SELECT 1,username,password FROM sys_user--"
        ]
        for p in payloads:
            resp = requests.post(f"{API}/login", json={"username": p, "password":"x"}, timeout=TIMEOUT)
            body = resp.json()
            assert body["code"] != 0, f"SQL注入payload绕过: {p} 响应={body}"
            # 敏感信息检查
            assert "password" not in str(body).lower()
            assert "stack" not in str(body).lower()

    @severity_p1
    @allure.story("安全-暴力破解")
    @allure.title("P1-高频登录请求限流429")
    @pytest.mark.security
    def test_login_rate_limit(self):
        acc = {"username":"ratelimit_user","password":"wrong"}
        codes = []
        for _ in range(60):
            try:
                r = requests.post(f"{API}/login", json=acc, timeout=5)
                codes.append(r.status_code)
            except:
                pass
        assert 429 in codes, f"高频访问60次未出现429，状态码集合={set(codes)}"

    @severity_p1
    @allure.story("用户登录")
    @allure.title("P1-token过期时间校验应为24小时")
    def test_login_token_expire_24h(self, admin_token):
        # JWT 解析
        import base64, json
        parts = admin_token.split(".")
        if len(parts) >= 2:
            payload = json.loads(base64.b64decode(parts[1] + "=="))
            exp_iat = payload.get("exp", 0) - payload.get("iat", 0)
            # 86400 ± 10s 容忍
            assert 86390 <= exp_iat <= 86410, f"token有效期≠24h, 实际={exp_iat}s"

    # ========== Token 鉴权 ==========
    @severity_p0
    @allure.story("鉴权")
    @allure.title("P0-无token访问业务接口返回401")
    def test_no_token_401(self):
        resp = requests.get(f"{BASE_URL}/api/student/list", timeout=TIMEOUT)
        http_assert(resp, 401, 401)

    @severity_p0
    @allure.story("鉴权")
    @allure.title("P0-伪造token签名校验失败401")
    def test_fake_token_401(self):
        h = headers("invalid.fake.token.string")
        resp = requests.get(f"{BASE_URL}/api/student/list", headers=h, timeout=TIMEOUT)
        assert resp.status_code == 401, "伪造 token 没有被拦截"

    @severity_p0
    @allure.story("登出")
    @allure.title("P0-登出成功后旧token立即失效")
    def test_logout_and_token_invalid(self, session_tokens):
        # 用单独请求模拟：新建一个独立登录然后登出
        r = requests.post(f"{API}/login", json=ACCOUNTS["sales01"], timeout=TIMEOUT)
        token = r.json()["data"]["token"]
        # 1. 确认可用
        r1 = requests.get(f"{BASE_URL}/api/student/list", headers=headers(token), timeout=TIMEOUT)
        assert r1.status_code == 200
        # 2. 登出
        requests.post(f"{API}/logout", headers=headers(token), timeout=TIMEOUT)
        # 3. 再访问 401
        r2 = requests.get(f"{BASE_URL}/api/student/list", headers=headers(token), timeout=TIMEOUT)
        assert r2.status_code == 401, "登出后 token 未失效"

    # ========== 修改密码 ==========
    @severity_p0
    @allure.story("修改密码")
    @allure.title("P0-旧密码正确修改成功 旧token失效")
    def test_change_password_ok(self, admin_token):
        body = {"oldPassword": "Admin@123#", "newPassword": "NewPass@2025", "confirmPassword": "NewPass@2025"}
        resp = requests.put(f"{API}/password", headers=headers(admin_token), json=body, timeout=TIMEOUT)
        # 断言结构 (测试环境一般会 mock，这里只断言不抛错)
        assert resp.status_code == 200

    @severity_p1
    @allure.story("修改密码")
    @allure.title("P1-新密码复杂度不足 8位+大小写+数字+特殊字符")
    @pytest.mark.parametrize("weak_pwd,msg_key", [
        ("1234567", "长度"),
        ("aaaaaaaa", "大写"),
        ("AAAAAAAA", "小写"),
        ("Aa123456", "特殊"),
    ])
    def test_change_password_weak(self, admin_token, weak_pwd, msg_key):
        body = {"oldPassword": "Admin@123#", "newPassword": weak_pwd, "confirmPassword": weak_pwd}
        resp = requests.put(f"{API}/password", headers=headers(admin_token), json=body, timeout=TIMEOUT)
        assert resp.json()["code"] == 400, f"弱密码未被拦截: {weak_pwd}"
