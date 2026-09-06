# JMeter 脚本说明（简化版结构说明，可直接导入或在 JMeter 中新建）

> 脚本名：`JMeter-核心场景.jmx`  
> 作者：苏绍彰  
> 压测目标：某教育 EMS V2.0 四大核心场景

---

## 一、Test Plan 结构

```
Test Plan / 某教育-核心场景压测 v1.0
│
├─ User Defined Variables
│    ├─ baseUrl = http://perf.example-ems.com:8080
│    ├─ dbHost = 192.168.1.101
│    ├─ dbUser = perf_root
│    ├─ dbPwd  = ********
│    └─ thinkTime_ms = 300
│
├─ [配置元件]
│    ├─ HTTP Cookie Manager
│    ├─ HTTP Request Defaults（server=baseUrl）
│    ├─ JDBC Connection Configuration（MySQL，pool=50，URL参数避免乱码）
│    └─ CSV Data Set Config（5万条 学生ID/课程ID/手机号，独立3个csv）
│
├─ [线程组 SC-01] 登录接口（15%业务量）
│    Ultimate Thread Group：10s起 500并发 持续10min
│    └─ POST /api/auth/login
│         ├─ JSON 提取器：$.data.token → admin_token
│         ├─ JSON 断言：$.code  == 0
│         └─ 响应时间断言：≤2000ms
│
├─ [线程组 SC-02] 学员列表搜索（20%）
│    Stepping Thread Group：50→100→300→500 每阶梯5min
│    └─ GET /api/student/list?page=1&size=10&keyword=${__CSVRead(keywords.csv,0)}
│         ├─ Header：Authorization = Bearer ${admin_token}
│         └─ JSON 断言：$.code==0 && $.data.records.size() ≤ 10
│
├─ [线程组 SC-04★] 创建报名订单（核心）
│    Ultimate Thread Group：三阶段
│       - 100 用户（5s 启动，持续 180s）
│       - 300 用户（10s 启动，持续 300s）
│       - 500 用户（20s 启动，持续 600s）
│    ├─ [Once Only] 登录获取 token
│    ├─ 同步定时器：Synchronizing Timer（集合点）：50 个用户一起下单，测并发冲突
│    ├─ 高斯随机思考时间 300~800ms
│    ├─ POST /api/enrollment
│    │    Body：{"studentId":${stuId_csv},"courseId":${courseId_csv},"hours":20,"__requestId":"${__UUID}"}
│    │    ├─ JSON 提取 orderId
│    │    ├─ JSON 断言 code==0
│    │    ├─ JSON 断言 data.payAmount==1800 （满减后金额）
│    │    └─ JSR223 断言：记录订单写入集合，做后续一致性对账
│    └─ [IF 50%] GET /api/enrollment/${orderId}
│
├─ [线程组 SC-07★] 财务日报查询（报表）
│    Concurrency Thread Group：目标 100 并发，hold 15min
│    └─ GET /api/report/finance/daily?date=${__RandomDate(,2025-04-01,2025-06-30,)}
│         ├─ JSON 断言：$.code==0
│         ├─ JDBC Request：SELECT IFNULL(SUM(pay_amount),0) FROM t_enrollment WHERE DATE(pay_time)=? 对比响应 total
│         └─ 响应时间断言 ≤ 5000ms
│
├─ [监听器]
│    ├─ View Results Tree（仅调试模式，正式关闭）
│    ├─ Summary Report
│    ├─ Aggregate Report
│    ├─ jp@gc - Response Times Over Time
│    ├─ jp@gc - Transactions per Second
│    ├─ jp@gc - Active Threads Over Time
│    ├─ PerfMon Metrics Collector（3 App + 1 DB 的 CPU/MEM/DISK/NET）
│    └─ Backend Listener → InfluxDB 2.0 / Grafana 实时大屏
│
└─ [ tearDown Thread Group ]
     压测结束后执行 SQL：重置 demo 数据（可选）
```

---

## 二、参数化 CSV 文件格式示例

### students.csv（5万学员ID造好，避免压测时重复创建）
```csv
studentId,parentOpenId,campusId
100001,oXy_abc_001,1
100002,oXy_abc_002,2
100003,oXy_abc_003,1
...
```

### courses.csv
```csv
courseId,classId,pricePerHour
1001,2001,100
1002,2002,200
1003,2003,150
```

---

## 三、命令行运行（无界面，推荐正式压测）

```bash
# 1) 准备：施压机上安装 JDK17 + JMeter 5.6.3 + plugins-manager
# 2) 运行：
jmeter -n -t JMeter-核心场景.jmx \
       -l result_500u_$(date +%Y%m%d_%H%M).jtl \
       -e -o ./report_html_500u \
       -Jthreads=500 -Jduration=3600 \
       -JbaseUrl=http://perf.example-ems.com:8080

# 参数说明：
#   -n 非GUI  -t jmx文件  -l jtl结果保存  -e -o 跑完生成HTML报告
#   -J 自定义参数覆盖脚本中的变量

# 3) 跑完 分析 .jtl / 或用 JMeter GUI 打开监听器查看
jmeter -g result.jtl -o report_retry
```

---

## 四、常见瓶颈排查思路（项目真实经验整理）

| 现象 | 可能原因 | 排查方向 |
|------|----------|----------|
| TPS 上不去 CPU 很低 | DB 慢查询锁住了线程 | 开启 MySQL slowlog，Explain 慢 SQL 加索引 |
| CPU 满 但 TPS 不高 | 应用 GC 频繁 / 代码热点 | jstack + Arthas trace，看 Top method |
| 并发 100 没问题 200 开始报错 500 | 数据库连接池耗尽 | HikariCP 配置 maxPoolSize=20 太小 → 调到 100 |
| 支付接口 RT 波动大 | Redis 热点 key | Redis 监控热点，本地缓存一层 |
| 报表查询 P95 20s 超 SLA | SQL 中 where 子查询 + Filesort | 建联合覆盖索引、物化视图、预计算 |
| 报名接口偶发数据不一致（多加课时） | 事务隔离级别 RR 下的并发更新丢失 | 改乐观锁（version字段）或 Redis 分布式锁 |
| 第 1 次登录很慢（2-3s）后续很快 | JIT 热身 + 连接池初始化 | 压测前加 30s 热身阶段 |

---

## 五、压测 Checklist

- [ ] 确认压测环境和 SIT/UAT/生产 **完全隔离**（域名、DB、Redis 都独立）
- [ ] 关闭 SIT 环境正在跑的自动化，避免互相干扰
- [ ] 施压机带宽、句柄 `ulimit -n 65535` 设置
- [ ] 监控服务正常，Grafana 大屏 URL 可访问
- [ ] 压测前 备份 DB，压测后一键回滚数据
- [ ] 开发、运维、DBA 进群 值守
- [ ] 每轮压测结束，记录 `环境版本+配置参数+核心指标` 到压测基线表
