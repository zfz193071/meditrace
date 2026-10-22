# MT-23 求职材料初稿证据

日期：2026-10-22。上一票 MT-20 离线实现已提交为 `33e2bb7`。本次为 MT-23 **初稿阶段**，不关闭工单；前置 MT-16／20／22 未全部验收，front matter 保持 TODO。未推送、未部署、未发送求职消息。

## 已交付

- 根目录 [英文 README](../../README.md)：面向转诊材料审核任务，提供本地 demo、视频、代码、架构、评估、运行方式、取舍、限制和许可证现状。旧诊断聊天不再被描述为当前产品定位，但明确说明旧入口尚未由 MT-21 退役。
- [材料索引](../portfolio/README.md)、[面试讲解](../portfolio/INTERVIEW.md)：90 秒介绍、约 7 分钟架构讲解、10 个追问答案，链接源代码、测试与失败记录；准确区分 AI 辅助实现和用户本人尚待确认的贡献／审查。
- [两类岗位素材](../portfolio/ROLE-MATERIALS.md)：AI 应用工程／全栈英文项目简介和简历要点。第一人称经历、英语能力、工作资格、本人代码贡献不自动填为事实。
- [岗位筛选和询问模板](../portfolio/JOB-SCREENING.md)：技术匹配、海外政策、签证支持、来源和核查日期分列。未填入未经核查的当前岗位；人在中国且需要支持的措辞有明确适用条件。
- [Discord／招聘询问草稿](../portfolio/OUTREACH.md)：仅文件，未发送。没有虚构公开 demo URL、客户、临床验证、合规或提效比例。
- [声明证据表](../portfolio/CLAIMS.md)：逐项追溯功能、版本、评估、个人贡献和剩余限制。
- [视频粗剪](../portfolio/media/referral-demo-rough-cut.mp4)、[脚本](../portfolio/VIDEO.md)、[英文字幕](../portfolio/media/referral-demo-en.srt)：1280×720 H.264、约 80 秒、静音、烧录字幕。明确标记“edited rough cut / offline synthetic / no AI calls”。

视频采用实际离线 UI 操作后采集的 8 个静态画面进行剪辑和阅读停留，**不是连续实时录屏**，没有假推理动画。路径为案例入口 → 双侧出生日期证据 → 保持未解决并填写原因 → 确认且保留身份警告 → 加载预置新版、旧结果只读 → 新版固定结果 → 新版确认导出 → 离线评估和限制。

实际导出的 [身份案例文本](../portfolio/media/confirmed-demo.txt) 保留 Identity unresolved；[新版文本](../portfolio/media/prepared-demo.txt) 包含 Source version 2。影片只是粗剪，不冒称旁白成片或完整 MT-23 最终验收。

## 验证

- 默认 Chrome DevTools profile 被另一会话占用，改用本任务专属无界面 Chrome + CDP；始终后台，未切换用户窗口或使用私人标签页。
- 编译真实 demo／review／evaluation 组件为离线 harness，脚本操作固定结果、人工决定、确认、导出和预置版本切换；没有模型／支付／私有 API 请求。详情见 [capture-audit.json](../portfolio/media/capture-audit.json)。
- FFmpeg 生成 H.264 MP4；ffprobe 检查约 79.93 秒、1280×720、1199 帧、8 个英文字幕段，媒体信息见 [media-check.json](../portfolio/media/media-check.json)。已完整解码检查，并目视检查关键画面和 [八镜头联系表](../portfolio/media/contact-sheet.png)。修正了初版字幕过大及确认摘要镜头定位问题，当前版本显示身份警告和导出控件。
- 从临时隔离副本移除 `.env*`，通过 `env -i` 去除 provider／backend 配置，保留原仓库相对目录和 offsets-golden 测试样本，复制已锁定依赖后执行前端 build：成功，包含 `/`、`/demo`、`/evaluation`、`/project`。这是**干净配置 + 复用依赖构建**，不是全新联网安装或实际 dev 服务访问验收。初次目录不完整和依赖外链造成的验证环境错误均已修正，没有修改产品代码以绕过类型检查。记录见 [clean-config-check.json](../portfolio/clean-config-check.json)。
- README 和求职包本地链接检查全部存在；未运行无关业务回归，因为本次未改应用业务逻辑。
- 未改原始合成语料、gold、评估分数，也未冒充完成真实模型评估。更新 CONFIGURATION 中已过时的“固定示例未实现”说明。
- 用户已有 `TASK-PREVISIT-SUMMARY.md` 保持未跟踪且未修改。

## 仍待最终阶段

MT-16／20／22 验收完成后复核全部指标与文案，按实际结果修订／重录受影响镜头，验证公开视频播放和 HTTPS 链接。当前没有经过确认的新版线上地址，不能把旧部署当作本版展示。

用户个人经历、具体贡献、英语能力、所在地和工作资格需本人确认；职位表没有实时职位推荐，签证模板只是询问措辞。根目录没有 LICENSE 文件，因此没有擅自添加 MIT 或其他授权；原 README 的 MIT 字样不被继续当作完整许可证。现有 fixture／字体许可证单独引用。

下一实施项按已确定顺序为 **MT-17 测试支付、会员和回调**。MT-20 真实评估和本票最终材料仍在原票保留，不因进入下一票视为完成。
