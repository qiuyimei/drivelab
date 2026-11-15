# DriveLab 智能驾驶工况仿真与辅助分析平台 V1.0

面向智能驾驶标定前期的轻量辅助工具。依据开发文档实现五类工况、动力学约束、实车日志对标、知识库辅助分析、记录管理与可打印 PDF 报告。

## 已实现功能

- 高速跟驰、弯道稳态、动态换道、紧急避障、城市路口五类标准案例。
- 行车、车辆和路面参数配置；0.1 秒时间步长计算，5–60 秒仿真时序。
- 停车距离、附着利用率、侧向加速度、横摆角速度、方向盘转角和估算制动压力。
- SVG 行车示意、播放与进度拖动、五类时序曲线和 CSV 导出。
- CSV / JSON / TXT / TSV 日志，单位换算、无效行清洗、排序去重、时间偏移和重叠区间插值。
- 四通道双曲线对标，MAE、RMSE、最大绝对误差、可配置容差。合成演示日志明确标注。
- 按账户隔离的 D1 工况记录，保存参数、日志、容差和分析快照；支持搜索、恢复和删除。
- 六份内置知识依据、自定义 TXT / Markdown / 粘贴资料、分段与词项向量检索。
- 默认确定性规则分析；配置兼容接口后启用大模型 RAG。未接入模型时页面如实显示。
- 页面内报告预览，使用“打印 / 保存 PDF”在浏览器中另存为 PDF，包含硬件对标结果。

## 技术栈

React 19 / TypeScript / Vinext / Vite / Cloudflare Workers / D1 / Drizzle。前后端共享纯计算模块，服务端重新校验输入与运算。

## 本机使用

桌面“DriveLab 开发工具”中保留了 Node.js、GitHub CLI、使用说明和原始安装包；GitHub Desktop 有独立桌面入口。桌面“启动 DriveLab”打开本机项目。

初次在其他电脑上运行：安装 Node.js 24 LTS 和 pnpm 11.25.0，再在项目目录执行：

```powershell
pnpm install --frozen-lockfile
pnpm test
pnpm run typecheck
pnpm run build
node --import ./scripts/sites-env.mjs ./node_modules/wrangler/bin/wrangler.js d1 execute DB --local --config dist/server/wrangler.json --persist-to .wrangler/state --file drizzle/0000_majestic_mulholland_black.sql
pnpm run dev
```

打开 http://127.0.0.1:5173/ 。本地保存和知识分析需要点击侧栏“登录”；这是仅用于回环预览的模拟账号，生产环境使用 Sites 账户登录。数据库位于忽略的 `.wrangler/state`，不上传 GitHub。已经应用过的迁移不要重复执行。

## 可选大模型

把 `.env.example` 复制为 `.dev.vars`，配置 `LLM_BASE_URL`（HTTPS，末尾不含 `/chat/completions`）、`LLM_MODEL`、`LLM_API_KEY`。生产环境通过 Sites 的服务端环境变量配置。密钥不得写入浏览器代码或提交 Git。

默认检索为 512 维中文单字/双字与英文词项哈希向量 + 余弦相似度，属于词项检索，不等同于语义 embedding。用户资料未经过工程审核。接入大模型后使用检索段落和当前计算结果生成引用分析。

## 日志格式

```csv
time_s,speed_kmh,yaw_rate_dps,brake_pressure_bar,steering_angle_deg
0,100,0,0,0
0.1,100,0,0,0
0.2,100,0,0,0
```

时间列必需，至少一个测量通道。支持 `timestamp_ms`、`speed_mps`、`yaw_rate_rad` 自动换算，也可在界面选择单位。采集时间先以首条有效时间归零，再加偏移。正偏移表示实车曲线向右移动；共同区间之外不外推。方向盘角统一为 °、压力统一为 bar。单次最多 5 MB / 20,000 行。

## API

| 接口 | 用途 |
| --- | --- |
| POST `/api/simulate` | 校验参数并返回完整仿真时序与约束 |
| GET `/api/status` | 存储与大模型配置状态（不返回密钥） |
| GET / POST `/api/records` | 当前账号的工况记录 |
| DELETE `/api/records/:id` | 删除当前账号拥有的记录 |
| GET / POST `/api/knowledge` | 当前账号的自定义知识资料 |
| DELETE `/api/knowledge/:id` | 删除当前账号拥有的资料 |
| POST `/api/analyze` | 当前工况的知识检索与规则 / 大模型分析 |

## 工程边界

本项目只做文件日志导入与预评估，不开发硬件驱动、嵌入式或感知规划控制算法。模型为水平路面恒减速、稳态圆周运动、运动学单轨与给定五次换道轨迹。摩擦圆只判断需求是否超限，不求解超限后的实际轨迹。忽略轮胎非线性、坡度、悬架和载荷转移。默认阈值及制动增益需要车辆工程人员确认。输出不构成车辆安全认证。

## GitHub 私有协作

保持仓库 Private。在 GitHub 仓库 `Settings → Collaborators → Add people` 中输入合作者的 GitHub 用户名；对方接受后即可访问、提交代码。仅邀请需要协作的那个人，无需公开仓库。日常推荐双方使用独立分支，通过 Pull Request 审核后合并。

阶段说明见 DEVELOPMENT.md。GitHub Actions 会在 push / pull request 时运行核心测试、类型检查与构建。
