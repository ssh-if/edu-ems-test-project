"""
某教育教务管理系统 - Pytest 接口自动化公共配置
Author: 苏绍彰
"""
import os
import json
import time
import random
import string
import pytest
import requests
import allure
from typing import Dict, Any

# ============== 环境配置 ==============
BASE_URL = os.getenv("ZW_BASE_URL", "http://test.example-ems.com:8080")
TIMEOUT = 15

# 测试账号（脱敏）
ACCOUNTS = {
    "admin":    {"username": "admin",    "password": "Admin@123#"},
    "sales01":  {"username": "sales01",  "password": "Sales@123"},
    "finance01":{"username": "finance01","password": "Finance@123"},
    "principal":{"username": "principal01", "password": "Principal@123"},
    "teacher":  {"username": "teacher01","password": "Teacher@123"},
}

# ============== Fixture ==============

@pytest.fixture(scope="session")
def session_tokens():
    """会话级别：所有角色登录一次拿 token，避免重复登录"""
    tokens: Dict[str, str] = {}
    for role, acc in ACCOUNTS.items():
        try:
            r = requests.post(
                f"{BASE_URL}/api/auth/login",
                json=acc,
                timeout=TIMEOUT,
            )
            if r.status_code == 200 and r.json().get("code") == 0:
                tokens[role] = r.json()["data"]["token"]
            else:
                tokens[role] = ""
                print(f"[WARN] {role} 登录失败: {r.text[:200]}")
        except Exception as e:
            tokens[role] = ""
            print(f"[ERROR] {role} 登录异常: {e}")
    yield tokens


@pytest.fixture(scope="function")
def admin_token(session_tokens) -> str:
    return session_tokens.get("admin", "")

@pytest.fixture(scope="function")
def sales_token(session_tokens) -> str:
    return session_tokens.get("sales01", "")

@pytest.fixture(scope="function")
def finance_token(session_tokens) -> str:
    return session_tokens.get("finance01", "")

@pytest.fixture(scope="function")
def principal_token(session_tokens) -> str:
    return session_tokens.get("principal", "")

@pytest.fixture(scope="function")
def teacher_token(session_tokens) -> str:
    return session_tokens.get("teacher", "")


# ============== 公共 HTTP 方法 ==============

def headers(token: str, ctype: str = "application/json") -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": ctype,
        "User-Agent": "Pytest-AutoTest/1.0 SuShaoZhang",
        "X-Request-Id": "TEST-" + "".join(random.choices(string.ascii_letters + string.digits, k=12)),
    }


def http_assert(resp: requests.Response, expected_code: int = 200,
                expected_biz_code: int = 0, msg_contains: str = None) -> Dict[str, Any]:
    """通用断言：HTTP 状态码 + 业务 code + msg 包含 + 响应结构"""
    assert resp.status_code == expected_code, \
        f"HTTP状态码不符 期望={expected_code} 实际={resp.status_code} 响应={resp.text[:500]}"
    try:
        body = resp.json()
    except Exception:
        raise AssertionError(f"响应非JSON格式: {resp.text[:300]}")
    assert "code" in body and "msg" in body and "data" in body, \
        f"响应缺少统一结构 code/msg/data: {body}"
    if expected_biz_code is not None:
        assert body["code"] == expected_biz_code, \
            f"业务code不符 期望={expected_biz_code} 实际={body['code']} msg={body.get('msg')}"
    if msg_contains:
        assert msg_contains in str(body.get("msg", "")), \
            f"msg 未包含关键字: 期望含'{msg_contains}' 实际='{body.get('msg')}'"
    return body


def random_mobile() -> str:
    """生成随机手机号"""
    return "139" + "".join(random.choices(string.digits, k=8))


def random_name() -> str:
    """生成随机学员名"""
    sur = "赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华金魏陶姜"
    giv = "伟芳娜秀英敏静丽强磊军洋勇艳杰娟涛明超秀兰霞平刚桂英文华建国志伟"
    return random.choice(sur) + "".join(random.choices(giv, k=2))


# ============== 公共数据校验 ==============

def assert_field_equal(actual, expected, field_name: str):
    assert actual == expected, f"字段[{field_name}]不符: 期望={expected} 实际={actual}"


# ============== Allure 用例标签 ==============

def severity_p0(func):
    return allure.severity(allure.severity_level.BLOCKER)(func)
def severity_p1(func):
    return allure.severity(allure.severity_level.CRITICAL)(func)
def severity_p2(func):
    return allure.severity(allure.severity_level.NORMAL)(func)
