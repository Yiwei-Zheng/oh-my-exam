# Oh My Exam

> 一套可复现的试卷智能处理系统: 自动发现和校验原始 PDF, 通过版面几何与 OCR 精确切题, 完成清洗、索引和原子发布, 最终生成可搜索、可追溯、带可解释相似题推荐的题库.

**简体中文** · [English](README.md)

![题库浏览器展示精确裁切的数学题](docs/readme-assets/question-browser.png)

---

## 这不只是一个题库

Oh My Exam 把一堆来源、年代、排版质量都不一致的试卷, 变成结构统一且可以检索、预览、推荐和审计的数据产品. 它同时包含:

- 面向学生和教师的双语题库浏览器;
- 面向管理员的题库更新、资产检查、账号和系统监控工作台;
- 不依赖 GUI、可独立从 CLI 运行的试卷处理流水线;
- 针对 CIE A Level、STEP、PAT、TMUA、ENGAA 和 NSAA 的来源适配器;
- 从原始 PDF 到题目 JPG、答案 JPG、文本、标签、相似题和 SQLite 发布目录的完整数据链路.

当前本地目录示例包含 24,136 道题、1,333 份试卷和 2,557 份源文档. 运行数据不提交到 Git, 实际规模取决于本地构建的 catalog.

![管理员后台总览](docs/readme-assets/admin-overview.png)

## 一条从互联网资料到可检索题库的流水线

```text
固定来源发现 / Source discovery
          ↓
并发下载 + SHA-256 校验 + 不可变原卷
          ↓
PDF 结构分析 ──→ 学科专用几何切题
          └────→ OCR / 栅格布局回退
          ↓
题目与答案配对 + 文本提取 + 规范化清洗
          ↓
元数据校验 + 可移植科目数据库
          ↓
Syllabus 标签 + 稀疏 TF-IDF 向量 + 相似题排序
          ↓
候选 catalog 完整性检查
          ↓
原子替换上线 / Atomic publication
```

每个阶段都可以单独执行、增量更新或覆盖重跑. Web 请求只创建持久化任务, 真正的处理由独立子进程完成; 页面关闭后任务记录仍然存在. 运行中的任务支持暂停与恢复, 并持续报告阶段、当前资源、耗时和预计剩余时间.

![试卷处理流水线工作台](docs/readme-assets/pipeline-workspace.png)

## 下载器: 快, 但不会把上游打挂

- 固定来源探测会先比较远端资源身份与本地不可变 PDF, 再由管理员确认下载.
- 多线程发现和下载由统一的自适应请求门控制. 连续成功时使用 AIMD 策略逐步扩大并发窗口; 遇到 HTTP 429/503 时窗口减半, 并尊重 `Retry-After` 冷却时间.
- 流水线并行度按逻辑处理器数量推荐, 可在 1-32 之间调整.
- 下载采用临时 `.part` 文件、重试、大小检查和 SHA-256 来源哈希, 避免半成品被误认为有效资料.
- 增量模式跳过已经完整存在的产物; 覆盖模式可以确定性重建指定阶段.

## 切题算法: 不相信单一规则

不同年代和考试机构的 PDF 差异非常大: 有的有完整文本层, 有的是整页扫描图, 有的旋转页面、双栏评分表或跨页长题. Oh My Exam 没有用一个脆弱的正则去赌所有格式, 而是组合多种证据.

### 1. 学科专用 PDF 几何切题

CIE 9709 Mathematics 和 9231 Further Mathematics 使用独立 cutter. 它们通过 PyMuPDF 读取:

- text blocks、words、spans 和字体位置;
- drawings、embedded images 和实际内容边界;
- page box、页面旋转以及显示坐标转换;
- 题号、子题编号、评分栏和跨页连续关系.

算法先在 PDF 对象坐标系中寻找可信锚点, 再构造跨页 crop regions. 对旋转页、整页图片、旧版评分方案和缺失题号分别有专门路径. 渲染后还会根据墨迹包围盒裁掉空白, 并执行内容覆盖审计, 防止图表、公式或题目尾部被悄悄切掉.

### 2. Raster layout 回退

文本层损坏或不可靠时, cutter 会把页面以更高比例渲染为灰度图, 通过阈值化、行/列投影和连通区域寻找题号与正文边界. 它保留 PDF 坐标与渲染像素之间的映射, 因而回退后仍能生成可追溯的裁剪区域.

### 3. OCR 驱动的扫描件切题

PAT 和 STEP 的历史扫描件会先尝试 PDF 文本块和单词锚点. 当检测到的题号序列不完整时, 系统调用 RapidOCR + ONNX Runtime 识别页面, 将 OCR 结果映射回 PDF 坐标, 再与原生文本候选合并并选择最长的可信题号序列.

- 如果 ONNX Runtime 检测到 `CUDAExecutionProvider`, OCR 自动使用 CUDA;
- GPU 初始化失败或机器没有兼容 GPU 时自动回退 CPU;
- OCR 页面结果带缓存, 避免同一页在锚点检测、空白判断和答案配对时重复推理;
- 检测结果必须通过连续编号、声明题数及 QP/MS 配对数量验证, 低置信度结果会明确失败, 而不是静默生成错误题目.

这意味着“硬件加速”用于真正计算密集的扫描件 OCR; 普通矢量 PDF 则直接利用结构化 layout, 不浪费算力做不必要的图像识别.

## 数据清洗与可追溯性

切出图片只是开始. 每道题的 sidecar manifest 会记录来源 URL、源 PDF SHA-256、cutter 名称和版本、页码、crop regions、渲染参数、图像尺寸以及文本提取来源.

处理阶段还会:

- 统一 Unicode、空白、换行和题号格式;
- 过滤大面积空白页和无意义片段;
- 从 PDF clips 提取可搜索文本, 必要时使用 OCR 补全;
- 将 question paper 与 mark scheme 按稳定身份配对;
- 对答案保存原始文本和规范化 Markdown;
- 验证 crop region schema、文档身份、图片存在性和题目/答案覆盖率;
- 使用并行 metadata loader 读取大量 sidecar, 同时保持确定性的输出顺序.

原始 PDF 始终是权威输入, 派生产物可以从 manifest 重建和审计.

## 相似题: 可解释的稀疏向量, 不是黑箱

当前实现没有伪装成“大模型语义搜索”, 也没有在 OCR 噪声较大的小语料上强行训练 Word2Vec. 它使用更适合当前数据质量的确定性混合排序:

1. 对规范化题目文本分词并去除高频功能词;
2. 构建 TF-IDF 稀疏向量并做 L2 归一化;
3. 借助倒排 posting lists 只累加共享词项的候选, 而不是暴力比较所有向量;
4. 使用 `75% × TF-IDF cosine + 25% × syllabus-topic Jaccard` 计算最终分数;
5. 排除同一份试卷中的题目, 避免把相邻小问当成推荐;
6. 文本证据不足时, 依次从共享知识点、同 component、同考试项目和全局题库补足结果.

知识点来自维护的 syllabus hierarchy, 同一道题可以拥有多个标签. 相似度在全局语料上构建, 因此 A Level 与 admissions 题目只要数学语言和知识点重合, 就能跨考试项目互相推荐. 数据库已经预留 embedding model 和 question embedding 表, 将来可以在不破坏现有 API 的前提下增加神经向量召回.

![可解释的相似题推荐](docs/readme-assets/similar-questions.png)

## 搜索与图片搜题

- 文本搜索覆盖题面、稳定身份、标签和 syllabus knowledge points.
- 知识点筛选按父子树展开, 选择一个分支会包含全部后代主题.
- 图片搜题接受拍照、文件、拖拽或剪贴板图片, 限制文件大小和总像素后调用 RapidOCR, 不可用时回退 Tesseract.
- OCR 输出经过分词、去重和停用词过滤后, 对全部命中候选计算余弦相似度, 最终返回最相关的五题.
- 题目预览可在切题 JPG、答案 JPG、结构化文本和带高亮区域的原始试卷页之间切换.

## 发布时不拿线上数据冒险

每次发布先在隔离路径构建 candidate SQLite catalog. 系统随后执行 SQLite `integrity_check`, 校验题目数量、预渲染题图、答案覆盖和资源关联. 只有全部通过时才用 `os.replace` 原子替换 active catalog; 任一检查失败都会保留上一版可用题库.

管理员对答案文本的修订采用 append-only version rows, 新版本立即生效, 历史版本保留用于审计和未来回滚.

## 产品能力

- Next.js + shadcn 响应式 Web 客户端, 支持中文、英文、明暗主题和键盘操作;
- FastAPI 后端, 默认拒绝未认证 API, 使用 HttpOnly cookie;
- Argon2 密码哈希、账户与 IP 双维度登录限流、管理员/教师/学生角色;
- 懒加载试卷树、cursor pagination、题目/答案/原卷联动预览;
- 可导出两页式题目与答案 PDF;
- 管理端 CPU、内存、磁盘和项目存储监控;
- SQLite 模块化单体架构, 前端、API、核心 pipeline 清晰解耦;
- CLI 与 Web 共用同一套核心处理服务.

## 快速开始

要求: Python 3.11+、Node.js 20.17+、npm. OCR 和 PDF 能力所需依赖由项目环境脚本安装.

```powershell
python scripts\setup_env.py --group all
Set-Location frontend
npm install
Set-Location ..
python start_server.py --local
```

打开 `http://127.0.0.1:4173`. 首次启动前, 参考 `.env.example` 设置管理员邮箱、管理员密码和 JWT secret.

## Pipeline CLI

核心 pipeline 不依赖 Web UI. 安装 backend editable package 后可以直接运行:

```text
ome-cie-alevel-downloader       ome-cie-alevel-splitter
ome-uat-admissions-downloader   ome-uat-admissions-splitter
ome-pat-admissions-downloader   ome-pat-admissions-splitter
ome-step-admissions-downloader  ome-step-admissions-splitter
ome-process-tmua
ome-pack-subject                ome-build-catalog
ome-match-questions
```

TMUA 提供可复现的一键端到端命令:

```powershell
Set-Location backend
..\.venv\Scripts\python scripts\process_tmua.py
```

使用 `--skip-download` 从本地不可变 PDF 重建, 或使用 `--skip-activate` 在生成科目数据库后停止.

## 验证

```powershell
Set-Location backend
..\.venv\Scripts\python -m pytest -q

Set-Location ..\frontend
npm run lint
npm run typecheck
npm run build
```

生产部署采用 Linux bare metal + systemd + Caddy. 运行数据库、原始试卷和切题产物位于 `backend/data/`, 不属于 Git 仓库内容. 详细设计见 [documentation index](docs/index.md) 和 [architecture](docs/architecture.md).
