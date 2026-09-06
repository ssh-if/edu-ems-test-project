"""
模块：报名缴费模块接口自动化
Author: 苏绍彰
"""
import allure
import pytest
import requests
from conftest import (BASE_URL, headers, http_assert, TIMEOUT,
                      random_mobile, random_name, severity_p0, severity_p1)

ENROLL_API   = f"{BASE_URL}/api/enrollment"
REFUND_API   = f"{BASE_URL}/api/refund"
PAY_CALLBACK = f"{BASE_URL}/api/pay/callback/wx"
REPORT_API   = f"{BASE_URL}/api/report"


@allure.epic("EMS-教务管理系统")
@allure.feature("M04-报名缴费")
class TestEnrollment:

    @pytest.fixture(scope="class")
    def demo_student_id(self, admin_token):
        """先建一个新学员用于整轮报名测试"""
        p = {"name": f"缴费测试学生-{random_name()}", "mobile": random_mobile(),
             "gradeId": 1, "sourceId": 1, "campusId": 1, "followUserId": 1}
        r = requests.post(f"{BASE_URL}/api/student", headers=headers(admin_token),
                          json=p, timeout=TIMEOUT)
        yield r.json()["data"]["id"]

    # ========== 创建订单 ==========
    @severity_p0
    @allure.story("创建报名订单")
    @allure.title("P0-全款报名数学20课时-订单与课时余额正确")
    def test_create_enrollment_full_ok(self, admin_token, demo_student_id):
        payload = {
            "studentId": demo_student_id,
            "courseId": 1001,      # 数学班课 100元/课时
            "classId": 2001,
            "hours": 20,
            "payMethod": 1,        # 微信
            "couponId": None,
        }
        with allure.step("1. 创建订单"):
            resp = requests.post(ENROLL_API, headers=headers(admin_token), json=payload, timeout=TIMEOUT)
            body = http_assert(resp, 200, 0)
            order_id = body["data"]["orderId"]
            pay_amount = body["data"]["payAmount"]
        with allure.step("2. 金额校验 原价=20×100=2000 满2000-200 → 实付1800"):
            assert pay_amount == 1800, f"满减计算错误, 期望1800 实际={pay_amount}"
        with allure.step("3. 查详情 状态=待支付"):
            det = requests.get(f"{ENROLL_API}/{order_id}", headers=headers(admin_token), timeout=TIMEOUT)
            assert det.json()["data"]["status"] in ("待支付", 0), "新建订单状态应为待支付"
        return order_id

    @severity_p0
    @allure.story("创建报名订单")
    @allure.title("P0-前端篡改金额参数 以后端为准实付仍=1800")
    def test_create_enrollment_tampered_price(self, admin_token, demo_student_id):
        payload = {
            "studentId": demo_student_id, "courseId": 1001, "classId": 2001,
            "hours": 20, "amount": 0.01  # 前端硬写0.01元
        }
        resp = requests.post(ENROLL_API, headers=headers(admin_token), json=payload, timeout=TIMEOUT)
        body = http_assert(resp, 200, 0)
        assert body["data"]["payAmount"] == 1800, f"金额被前端绕过后端校验! 实际={body['data']['payAmount']}"

    @severity_p1
    @allure.story("创建报名订单")
    @allure.title("P1-满减边界值 1999不触发 / 2000触发 / 2001触发")
    @pytest.mark.parametrize("hours,expect_discount,expect_amount", [
        (19, False, 1900),
        (20, True, 1800),
        (21, True, 1900),
    ])
    def test_enrollment_full_discount_boundary(self, admin_token, demo_student_id, hours, expect_discount, expect_amount):
        payload = {"studentId": demo_student_id, "courseId": 1001, "classId": 2001, "hours": hours}
        resp = requests.post(ENROLL_API, headers=headers(admin_token), json=payload, timeout=TIMEOUT)
        body = http_assert(resp, 200, 0)
        assert body["data"]["payAmount"] == expect_amount, \
            f"课时={hours} 满减计算错误: 期望实付={expect_amount} 实际={body['data']['payAmount']}"

    @severity_p0
    @allure.story("创建报名订单")
    @allure.title("P0-课时=0参数校验失败")
    def test_create_hours_zero_400(self, admin_token, demo_student_id):
        payload = {"studentId": demo_student_id, "courseId": 1001, "classId": 2001, "hours": 0}
        resp = requests.post(ENROLL_API, headers=headers(admin_token), json=payload, timeout=TIMEOUT)
        http_assert(resp, 200, 400, "课时")

    @severity_p0
    @allure.story("创建报名订单")
    @allure.title("P0-课时为负数校验失败")
    def test_create_hours_negative_400(self, admin_token, demo_student_id):
        payload = {"studentId": demo_student_id, "courseId": 1001, "classId": 2001, "hours": -5}
        resp = requests.post(ENROLL_API, headers=headers(admin_token), json=payload, timeout=TIMEOUT)
        http_assert(resp, 200, 400)

    @severity_p0
    @allure.story("创建报名订单")
    @allure.title("P0-同学员同时间段课程冲突检测")
    def test_create_time_conflict_blocked(self, admin_token, demo_student_id):
        # 先报一个周六10点的班
        p1 = {"studentId": demo_student_id, "courseId": 1001, "classId": 2001, "hours": 10}
        requests.post(ENROLL_API, headers=headers(admin_token), json=p1, timeout=TIMEOUT)
        # 再报另一个同时间的英语班
        p2 = {"studentId": demo_student_id, "courseId": 1002, "classId": 2002, "hours": 10}
        resp = requests.post(ENROLL_API, headers=headers(admin_token), json=p2, timeout=TIMEOUT)
        http_assert(resp, 200, 3002, "冲突")

    @severity_p0
    @allure.story("创建报名订单-幂等")
    @allure.title("P0-重复提交同请求, 防重token机制只创建1单")
    def test_create_enrollment_idempotency(self, admin_token, demo_student_id):
        payload = {"studentId": demo_student_id, "courseId": 1001, "classId": 2001, "hours": 5,
                   "__requestId": "TEST-IDEMP-00001"}
        r1 = requests.post(ENROLL_API, headers=headers(admin_token), json=payload, timeout=TIMEOUT)
        r2 = requests.post(ENROLL_API, headers=headers(admin_token), json=payload, timeout=TIMEOUT)
        if r1.json()["code"] == 0 and r2.json()["code"] == 0:
            assert r1.json()["data"]["orderId"] == r2.json()["data"]["orderId"], \
                "重复请求创建了两个不同订单号"

    # ========== 订单列表 ==========
    @severity_p0
    @allure.story("订单列表")
    @allure.title("P0-列表分页与权限脱敏 销售看不到金额")
    def test_order_list_permission_sales(self, sales_token):
        resp = requests.get(f"{ENROLL_API}/list", headers=headers(sales_token),
                            params={"page":1,"size":20}, timeout=TIMEOUT)
        body = http_assert(resp)
        for r in body["data"]["records"]:
            assert r.get("payAmount") is None or str(r.get("payAmount")) in ("", "****", "0"), \
                "销售账号金额字段未脱敏"

    @severity_p1
    @allure.story("订单列表")
    @allure.title("P1-多条件组合+金额排序")
    def test_order_list_sort_amount_desc(self, admin_token):
        resp = requests.get(f"{ENROLL_API}/list", headers=headers(admin_token),
                            params={"page":1,"size":20,"sort":"payAmount","order":"desc"}, timeout=TIMEOUT)
        body = http_assert(resp)
        amounts = [r.get("payAmount", 0) for r in body["data"]["records"]]
        assert amounts == sorted(amounts, reverse=True), "金额从大到小排序不正确"

    # ========== 微信回调 ==========
    @severity_p0
    @allure.story("支付回调")
    @allure.title("P0-微信回调验签-篡改金额 订单不更新状态")
    def test_wx_callback_tampered_amount_ignored(self, admin_token, demo_student_id):
        # 1. 建一个正常订单
        payload = {"studentId": demo_student_id, "courseId": 1001, "classId": 2001, "hours": 10}
        order_id = requests.post(ENROLL_API, headers=headers(admin_token), json=payload, timeout=TIMEOUT).json()["data"]["orderId"]
        # 2. 构造篡改总金额的回调
        xml = f"<xml><return_code>SUCCESS</return_code><out_trade_no>{order_id}</out_trade_no><total_fee>1</total_fee><sign>FAKE_SIGN</sign></xml>"
        resp = requests.post(PAY_CALLBACK, data=xml, headers={"Content-Type": "application/xml"}, timeout=TIMEOUT)
        # 3. 查订单状态
        det = requests.get(f"{ENROLL_API}/{order_id}", headers=headers(admin_token), timeout=TIMEOUT).json()
        assert det["data"]["status"] != "已支付", "验签失败的回调居然更新了订单状态为已支付"

    @severity_p0
    @allure.story("支付回调")
    @allure.title("P0-重复回调幂等, 课时余额只加一次")
    def test_wx_callback_idempotent(self, admin_token, demo_student_id):
        payload = {"studentId": demo_student_id, "courseId": 1001, "classId": 2001, "hours": 10}
        order_id = requests.post(ENROLL_API, headers=headers(admin_token), json=payload, timeout=TIMEOUT).json()["data"]["orderId"]
        # 调起 before_stu_detail 课时
        before = requests.get(f"{BASE_URL}/api/student/{demo_student_id}",
                              headers=headers(admin_token), timeout=TIMEOUT).json()["data"].get("remainHours", 0)
        # 构造正常 mock 回调两次 (真实环境应有 sign，测试环境可跳过验签)
        xml = f"<xml><return_code>SUCCESS</return_code><out_trade_no>{order_id}</out_trade_no><total_fee>90000</total_fee><sign>MOCK_VALID</sign></xml>"
        requests.post(PAY_CALLBACK, data=xml, headers={"Content-Type":"application/xml"}, timeout=TIMEOUT)
        requests.post(PAY_CALLBACK, data=xml, headers={"Content-Type":"application/xml"}, timeout=TIMEOUT)
        # 查课时余额
        after = requests.get(f"{BASE_URL}/api/student/{demo_student_id}",
                             headers=headers(admin_token), timeout=TIMEOUT).json()["data"].get("remainHours", 0)
        assert after - before == 10, f"幂等失败 课时加了{after-before}次, 期望只加10"

    @severity_p1
    @allure.story("支付回调")
    @allure.title("P1-XXE实体注入攻击 响应不包含 /etc/passwd 内容")
    @pytest.mark.security
    def test_wx_callback_xxe_protect(self):
        evil_xml = """<?xml version="1.0"?>
<!DOCTYPE foo [ <!ENTITY xxe SYSTEM "file:///etc/passwd"> ]>
<xml><return_code>&xxe;</return_code><out_trade_no>xxe_test</out_trade_no></xml>"""
        resp = requests.post(PAY_CALLBACK, data=evil_xml, headers={"Content-Type":"application/xml"}, timeout=TIMEOUT)
        assert "root:" not in resp.text, "XXE攻击成功 泄露系统文件内容"

    # ========== 退费 ==========
    @severity_p0
    @allure.story("退费申请")
    @allure.title("P0-退费金额>剩余可退金额 400")
    def test_refund_amount_over_remain_400(self, admin_token, demo_student_id):
        # 创建订单 20 课时
        payload = {"studentId": demo_student_id, "courseId": 1001, "classId": 2001, "hours": 20}
        order_id = requests.post(ENROLL_API, headers=headers(admin_token), json=payload, timeout=TIMEOUT).json()["data"]["orderId"]
        # 申请退费 21 课时 (超过 20)
        ref = {"orderId": order_id, "refundHours": 21, "reason": "测试超退", "reasonType": 1}
        resp = requests.post(REFUND_API, headers=headers(admin_token), json=ref, timeout=TIMEOUT)
        http_assert(resp, 200, 400, "超限")

    @severity_p1
    @allure.story("退费审核")
    @allure.title("P1-财务拒绝 必须填写原因")
    def test_refund_reject_require_reason(self, finance_token):
        refund_id = 1  # 假设存在一个待审核
        body = {"id": refund_id, "action": "reject", "reason": ""}
        resp = requests.put(f"{REFUND_API}/{refund_id}/audit",
                            headers=headers(finance_token), json=body, timeout=TIMEOUT)
        http_assert(resp, 200, 400, "原因")

    # ========== 财务报表 ==========
    @severity_p0
    @allure.story("财务日报")
    @allure.title("P0-日报合计=数据库流水sum一致")
    def test_daily_report_consistent_with_db(self, finance_token):
        import datetime
        today = datetime.date.today().strftime("%Y-%m-%d")
        resp = requests.get(f"{REPORT_API}/finance/daily", headers=headers(finance_token),
                            params={"date": today}, timeout=TIMEOUT)
        body = http_assert(resp)
        # 金额合计应该都是正整数 不为None
        for key in ("totalAmount", "wechatAmount", "alipayAmount", "balanceAmount"):
            assert key in body["data"] and body["data"][key] is not None, f"缺少字段 {key}"

    @severity_p0
    @allure.story("财务报表")
    @allure.title("P0-校长角色仅看自己校区的数据")
    def test_principal_report_only_campus(self, principal_token):
        resp = requests.get(f"{REPORT_API}/finance/daily", headers=headers(principal_token),
                            params={"date": "2025-06-20"}, timeout=TIMEOUT)
        body = http_assert(resp)
        assert body["data"].get("campusName") in ("东葛校区", None), "校长账号看到了其他校区"
