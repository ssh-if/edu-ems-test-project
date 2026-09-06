"""
模块：学员管理接口自动化测试
Author: 苏绍彰
"""
import allure
import pytest
import requests
from conftest import (BASE_URL, headers, http_assert, TIMEOUT,
                      random_mobile, random_name, severity_p0, severity_p1, assert_field_equal)

API = f"{BASE_URL}/api/student"


@allure.epic("EMS-教务管理系统")
@allure.feature("M02-学员管理")
class TestStudent:

    # ========== 列表查询 ==========
    @severity_p0
    @allure.story("学员列表")
    @allure.title("P0-分页查询默认page=1 size=10")
    @pytest.mark.smoke @pytest.mark.student
    def test_list_default(self, admin_token):
        resp = requests.get(f"{API}/list", headers=headers(admin_token),
                            params={"page": 1, "size": 10}, timeout=TIMEOUT)
        body = http_assert(resp)
        assert len(body["data"]["records"]) <= 10
        assert body["data"]["current"] == 1
        assert "total" in body["data"]

    @severity_p1
    @allure.story("学员列表")
    @allure.title("P1-page=0自动修正或返回空不500")
    def test_list_page_0_boundary(self, admin_token):
        resp = requests.get(f"{API}/list", headers=headers(admin_token),
                            params={"page": 0, "size": 10}, timeout=TIMEOUT)
        assert resp.status_code == 200, f"page=0 居然500: {resp.text[:300]}"

    @severity_p0
    @allure.story("学员列表")
    @allure.title("P0-size=10000上限截断防拖库")
    def test_list_size_limit(self, admin_token):
        resp = requests.get(f"{API}/list", headers=headers(admin_token),
                            params={"page": 1, "size": 10000}, timeout=TIMEOUT)
        body = http_assert(resp)
        assert len(body["data"]["records"]) <= 500, f"size上限未截断: {len(body['data']['records'])}"

    @severity_p0
    @allure.story("学员列表")
    @allure.title("P0-销售角色只能查看自己跟进的学员(数据权限)")
    def test_list_data_permission_sales(self, sales_token):
        resp = requests.get(f"{API}/list", headers=headers(sales_token),
                            params={"page":1,"size":100}, timeout=TIMEOUT)
        body = http_assert(resp)
        sales_id = 2  # sales01 的用户id
        for r in body["data"]["records"]:
            assert r["followUserId"] == sales_id, \
                f"越权! 销售看到了他人跟进的学员: followUserId={r['followUserId']}"

    @severity_p0
    @allure.story("学员列表")
    @allure.title("P0-按手机号精确搜索")
    def test_list_search_mobile(self, admin_token):
        mobile = "138****0000"
        resp = requests.get(f"{API}/list", headers=headers(admin_token),
                            params={"page":1,"size":10,"keyword":mobile}, timeout=TIMEOUT)
        body = http_assert(resp)
        for r in body["data"]["records"]:
            assert mobile in r["mobile"], f"搜索结果不符 期望含{mobile} 实际={r['mobile']}"

    @severity_p1
    @allure.story("学员列表")
    @allure.title("P1-多条件组合查询(校区+状态+来源)")
    def test_list_multi_condition(self, admin_token):
        params = {"campusId":1,"status":"在读","sourceId":1,"page":1,"size":20}
        resp = requests.get(f"{API}/list", headers=headers(admin_token), params=params, timeout=TIMEOUT)
        body = http_assert(resp)
        for r in body["data"]["records"]:
            assert r["campusId"] == 1
            assert r["status"] == "在读"

    @severity_p1
    @allure.story("学员列表")
    @allure.title("P1-按创建时间倒序排序")
    def test_list_sort_create_time_desc(self, admin_token):
        resp = requests.get(f"{API}/list", headers=headers(admin_token),
                            params={"sort":"createTime","order":"desc","page":1,"size":20}, timeout=TIMEOUT)
        body = http_assert(resp)
        times = [r["createTime"] for r in body["data"]["records"]]
        assert times == sorted(times, reverse=True), "倒序排列不正确"

    # ========== 新增学员 ==========
    @severity_p0
    @allure.story("新增学员")
    @allure.title("P0-完整参数新增学员成功")
    @pytest.mark.p0
    def test_create_student_ok(self, admin_token):
        payload = {
            "name": random_name(),
            "mobile": random_mobile(),
            "gender": 1,
            "gradeId": 3,
            "sourceId": 1,
            "campusId": 1,
            "followUserId": 1,
            "birthday": "2015-06-01"
        }
        with allure.step(f"新增学员 payload={payload}"):
            resp = requests.post(f"{API}", headers=headers(admin_token), json=payload, timeout=TIMEOUT)
        body = http_assert(resp, 200, 0)
        assert body["data"]["id"] and body["data"]["id"] > 0

    @severity_p0
    @allure.story("新增学员")
    @allure.title("P0-重复手机号必须拦截返回2001")
    def test_create_student_duplicate_mobile(self, admin_token):
        mobile = random_mobile()
        p = {"name":"测试A","mobile":mobile,"gradeId":1,"sourceId":1,"campusId":1,"followUserId":1}
        requests.post(f"{API}", headers=headers(admin_token), json=p, timeout=TIMEOUT)
        p2 = {"name":"测试B","mobile":mobile,"gradeId":1,"sourceId":1,"campusId":1,"followUserId":1}
        resp = requests.post(f"{API}", headers=headers(admin_token), json=p2, timeout=TIMEOUT)
        http_assert(resp, 200, 2001, "已存在")

    @severity_p0
    @allure.story("新增学员")
    @allure.title("P0-越权-无新增权限用户POST新增返回403")
    def test_create_student_no_permission_403(self, teacher_token):
        p = {"name":"越权测试","mobile":random_mobile(),"gradeId":1,"sourceId":1,"campusId":1,"followUserId":1}
        resp = requests.post(f"{API}", headers=headers(teacher_token), json=p, timeout=TIMEOUT)
        assert resp.status_code == 403, f"教师角色不应有新增权限 实际={resp.status_code}"

    @severity_p1
    @allure.story("新增学员")
    @allure.title("P1-姓名为空参数校验400")
    def test_create_name_empty_400(self, admin_token):
        p = {"name":"","mobile":random_mobile(),"gradeId":1,"sourceId":1,"campusId":1,"followUserId":1}
        resp = requests.post(f"{API}", headers=headers(admin_token), json=p, timeout=TIMEOUT)
        http_assert(resp, 200, 400, "姓名")

    @severity_p1
    @allure.story("新增学员")
    @allure.title("P1-手机号12位边界值400")
    def test_create_mobile_12_len(self, admin_token):
        p = {"name":"边界","mobile":"138****00001","gradeId":1,"sourceId":1,"campusId":1,"followUserId":1}
        resp = requests.post(f"{API}", headers=headers(admin_token), json=p, timeout=TIMEOUT)
        http_assert(resp, 200, 400, "手机")

    # ========== 安全 ==========
    @severity_p0
    @allure.story("新增学员-XSS")
    @allure.title("P0-姓名<script>标签XSS过滤")
    @pytest.mark.security
    def test_create_xss_filter(self, admin_token):
        p = {"name":"<script>alert(1)</script>","mobile":random_mobile(),"gradeId":1,"sourceId":1,"campusId":1,"followUserId":1}
        resp = requests.post(f"{API}", headers=headers(admin_token), json=p, timeout=TIMEOUT)
        assert "<script>" not in resp.text, "响应包含未过滤<script>"

    @severity_p0
    @allure.story("列表搜索-SQL注入")
    @allure.title("P0-搜索框SQL注入: ' OR 1=1 不返回全量")
    @pytest.mark.security
    def test_search_sql_injection(self, admin_token):
        resp_nor = requests.get(f"{API}/list", headers=headers(admin_token),
                                params={"keyword":"张三","page":1,"size":1000}, timeout=TIMEOUT).json()
        resp_inj = requests.get(f"{API}/list", headers=headers(admin_token),
                                params={"keyword":"' OR 1=1 --","page":1,"size":1000}, timeout=TIMEOUT)
        assert resp_inj.status_code == 200
        data = resp_inj.json()
        assert data["code"] != 0 or data["data"]["total"] <= resp_nor["data"]["total"], \
            "SQL注入后数量异常增大 疑似被拖库"

    # ========== 编辑 ==========
    @severity_p0
    @allure.story("编辑学员")
    @allure.title("P0-编辑成功字段更新")
    def test_edit_student_ok(self, admin_token, created_student_id):
        p = {"id": created_student_id, "name": "修改后姓名"}
        resp = requests.put(f"{API}/{created_student_id}", headers=headers(admin_token), json=p, timeout=TIMEOUT)
        http_assert(resp, 200, 0)
        # 再查一次
        detail = requests.get(f"{API}/{created_student_id}", headers=headers(admin_token), timeout=TIMEOUT).json()
        assert_field_equal(detail["data"]["name"], "修改后姓名", "姓名")

    @severity_p0
    @allure.story("编辑学员")
    @allure.title("P0-越权编辑其他校区学员返回403")
    def test_edit_cross_campus_403(self, sales_token):
        # 琅东校区学员 id 假设 sales01 属东葛校区
        langdong_student_id = 99999
        resp = requests.put(f"{API}/{langdong_student_id}", headers=headers(sales_token),
                            json={"id":langdong_student_id,"name":"越权修改"}, timeout=TIMEOUT)
        assert resp.status_code == 403, "跨校区编辑越权未拦截"

    # ========== 删除 ==========
    @severity_p0
    @allure.story("删除学员")
    @allure.title("P0-软删除数据库deleted=1")
    def test_delete_soft(self, admin_token, created_student_id):
        resp = requests.delete(f"{API}/{created_student_id}", headers=headers(admin_token), timeout=TIMEOUT)
        http_assert(resp, 200, 0)
        # 列表不再出现
        listr = requests.get(f"{API}/list", headers=headers(admin_token),
                             params={"page":1,"size":10}, timeout=TIMEOUT).json()
        ids = [r["id"] for r in listr["data"]["records"]]
        assert created_student_id not in ids, "软删除后学员仍出现在正常列表"

    @severity_p0
    @allure.story("删除学员")
    @allure.title("P0-有报名订单的学员不允许删除")
    def test_delete_with_order_blocked(self, admin_token):
        # 已知有订单学员id
        student_with_order_id = 100500
        resp = requests.delete(f"{API}/{student_with_order_id}", headers=headers(admin_token), timeout=TIMEOUT)
        http_assert(resp, 200, 3001, "订单")

    # ========== 详情脱敏 ==========
    @severity_p1
    @allure.story("学员详情")
    @allure.title("P1-销售身份看手机号中间4位必须脱敏")
    def test_detail_mobile_desensitize(self, sales_token, created_student_id):
        resp = requests.get(f"{API}/{created_student_id}", headers=headers(sales_token), timeout=TIMEOUT)
        body = http_assert(resp)
        mobile = str(body["data"]["mobile"])
        assert "****" in mobile or len(mobile.replace("*","")) < 11, \
            f"销售角色手机号未脱敏: {mobile}"

    # ========== fixture ==========
    @pytest.fixture(scope="class")
    def created_student_id(self, admin_token):
        p = {"name":"被编辑测试","mobile":random_mobile(),"gradeId":1,"sourceId":1,"campusId":1,"followUserId":1}
        r = requests.post(f"{API}", headers=headers(admin_token), json=p, timeout=TIMEOUT)
        sid = r.json()["data"]["id"]
        yield sid
        # 清理
        requests.delete(f"{API}/{sid}", headers=headers(admin_token), timeout=TIMEOUT)
