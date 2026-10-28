# Zotero PDF2zh 本地改版

本项目提供两种翻译论文 PDF 的方式：

| 方式 | 适合的场景 | 译文从哪里来 | 结果如何进入 Zotero |
|---|---|---|---|
| **Codex 论文翻译 skill** | 在对话中让 Codex 翻译论文，并指定纯中文或中英对照格式 | Codex 将原文分段翻译，`pdf2zh_next` 负责排版 | 指明要添加到 Zotero；也可以手动导入生成的 PDF |
| **Zotero 插件 + Server** | 在 Zotero 右键菜单中直接翻译 | 插件中选择的翻译服务 | 翻译完成后由插件添加附件 |

两种方式都可以生成纯中文版和中英对照版，但配置和使用流程不同。skill 不需要启动本项目的 Server；Zotero 插件的右键翻译需要 Server 和插件内配置的翻译服务。

skill 使用 `pdf2zh_next --clitranslator` 接收模型预先写好的译文，无须另配翻译 API Key。Codex 或其他模型本身是否收费取决于所使用的服务；首次安装或运行时也可能需要联网下载依赖和模型资源。

上游插件的完整说明见 [README.upstream.md](README.upstream.md)。

## 一、准备环境

以下命令以 Windows PowerShell 为例，从项目根目录执行。先安装 Zotero、Python 3.12 和 [uv](https://docs.astral.sh/uv/)，或使用已有的相应环境。项目目录可以位于任意位置，命令中的 `$PWD` 指当前项目根目录。

### 翻译引擎环境

skill 需要包含 `pdf2zh_next` 和 PyMuPDF 的 Python 环境。已有 `server\zotero-pdf2zh-next-venv` 时可以直接使用；没有时可创建：

```powershell
$Project = $PWD.Path
$EngineEnv = Join-Path $Project 'server\zotero-pdf2zh-next-venv'

uv venv "$EngineEnv" --python 3.12
uv pip install --python "$EngineEnv\Scripts\python.exe" 'pdf2zh_next>=2.9.0,<3.0.0' 'bitstring<5' PyMuPDF pypdf
```

这个环境与运行 Server 的 `server\venv` 是两个不同环境。通过项目 Server 管理环境时，也可以使用其创建的翻译引擎环境；默认配置示例见 [server/config/venv.json.example](server/config/venv.json.example)。

### 将 skill 安装到 Codex

项目中的 skill 位于 [.dsh/skills/pdf-paper-translate](.dsh/skills/pdf-paper-translate)。如 Codex 尚未发现它，可将其复制到当前用户的 Codex skills 目录：

```powershell
$Source = Join-Path $PWD.Path '.dsh\skills\pdf-paper-translate'
$Installed = Join-Path $env:USERPROFILE '.codex\skills\pdf-paper-translate'
$InstalledScripts = Join-Path $Installed 'scripts'
New-Item -ItemType Directory -Force -Path $InstalledScripts | Out-Null
Copy-Item -LiteralPath "$Source\SKILL.md" -Destination $Installed -Force
Copy-Item -Path "$Source\scripts\*" -Destination $InstalledScripts -Force
```

这是复制操作；日后修改项目中的 skill 后，需要重新同步到安装目录才能供已安装的版本使用。上述命令保留安装目录中已有的翻译记忆文件。重启或重新打开 Codex 会话后，可让 Codex 使用 `pdf-paper-translate`。项目内的 [SKILL.md](.dsh/skills/pdf-paper-translate/SKILL.md) 是面向助手的完整执行流程。

## 二、在 Codex 中翻译论文

提供 PDF 路径或附件，并说明需要的格式。例如：

> 使用 pdf-paper-translate 翻译这篇论文，生成纯中文和左右双栏中英对照，并添加到 Zotero 原论文条目下。图内文字和参考文献保留原文，翻译图注。

Codex 会使用翻译引擎提取文本、翻译待处理段落、生成 PDF。默认生成两种格式；如果只需要纯中文，可以明确提出。整个过程可能需要几分钟，耗时取决于 PDF 页数、文本量和本机排版速度。

| 输出文件 | 含义 |
|---|---|
| `*.mono.pdf` | 纯中文版 |
| `*.dual.pdf` | 默认左右双栏：原文与中文并排 |
| `*.LR_dual.pdf` | 明确标记为左右双栏的中英对照 |
| `*.TB_dual.pdf` | 原文和译文逐页交替的中英对照 |

生成双栏和纯中文版时，skill 使用同一份译文表；`--mono-only` 只生成纯中文版。它们不是分别翻译两遍。PDF 中的原文页保留原始语言，中文页使用相同的翻译结果。

默认处理规则是翻译正文和图注，保留公式、图内文字及参考文献。参考文献过滤依赖文本特征，图中文字是否需要跳过要结合原图判断；相同文本若同时出现在正文和图内，当前按文本查表的方式无法单独区分这两个位置。

## 三、手动运行 skill 脚本

这部分适用于需要自行控制每一步的用户。脚本不会自动调用模型生成译文：第 3 步必须由 Codex 或人工写入中文译文。

先在 PowerShell 中设置路径。将示例 PDF 替换为实际文件，每篇论文使用独立工作目录：

```powershell
$Project = $PWD.Path
$Skill = Join-Path $Project '.dsh\skills\pdf-paper-translate'
$Venv = Join-Path $Project 'server\zotero-pdf2zh-next-venv'
$Py = Join-Path $Venv 'Scripts\python.exe'
$Pdf = 'D:\papers\paper.pdf'
$Work = Join-Path $Project 'server\manual-translate\paper-01'
$Out = Join-Path $Work 'out'
```

如需使用已安装的 skill，将 `$Skill` 改为安装目录即可。用当前用户本机实际存在的环境替换 `$Venv`。

### 1. 提取并筛选段落

```powershell
& $Py "$Skill\scripts\run.py" --pdf "$Pdf" --venv "$Venv" --work "$Work" --capture
& $Py "$Skill\scripts\prepare.py" --work "$Work"
& $Py "$Skill\scripts\show.py" --work "$Work" --start 0 --count 30
```

`show.py` 以 `###内容ID|字符数` 开头显示每段原文。继续查看下一批时，将 `--start` 改为 `30`、`60` 等。`prepare.py` 会将可能不需要翻译的段落写入 `skipped.jsonl`，其余段落写入 `todo.json`；两者都是每行一条记录的 JSONL 文件。

对于提取出来的图内文字和未被识别的参考文献，先根据原 PDF 找到对应内容 ID，再标记为跳过；不要把图注一起跳过：

```powershell
& $Py "$Skill\scripts\prepare.py" --work "$Work" --skip-ids '图内文字ID1,图内文字ID2'
```

需要查看跳过项或恢复误判内容时：

```powershell
& $Py "$Skill\scripts\prepare.py" --work "$Work" --show-skipped
& $Py "$Skill\scripts\prepare.py" --work "$Work" --restore '需要恢复的ID'
```

### 2. 写入中文译文

将 `todo.json` 中的每个待译内容翻译后，按 ID 写入 `$Work\src.jsonl`。每行一个 JSON 对象，文件使用 UTF-8 编码，例如：

```jsonl
{"id": "这里填写show.py显示的ID", "t": "这里填写对应的中文译文。"}
```

- ID 使用 `show.py` 显示的内容 ID，不使用段落序号。
- 原文中的 `{v1}`、`{v2}` 等占位符要按原有顺序和数量保留，以便排版时放回公式等内容。
- 保留引用标记、数字和必要的专有名词。图注需要翻译，图内标签与参考文献通常保留原文。
- 每个待译 ID 都需要对应译文；不要将 `show.py` 的输出标记或本例中的占位 ID 当作真实 ID。

### 3. 构建译文表并生成 PDF

```powershell
& $Py "$Skill\scripts\build.py" --work "$Work"
& $Py "$Skill\scripts\run.py" --pdf "$Pdf" --venv "$Venv" --work "$Work" --out "$Out"
```

`build.py` 会将译文写入 `translations.jsonl`，并检查缺失、占位符、明显未翻译内容和乱码替换字符。如果它报错，按输出中的 ID 修改 `src.jsonl` 后重新构建。生成时默认输出纯中文和双栏对照 PDF 到 `$Out`。

只需要纯中文版时，在生成命令末尾加 `--mono-only`。`--verify` 是**单独验证已有输出**的模式，不要与生成命令合并使用：

```powershell
& $Py "$Skill\scripts\run.py" --venv "$Venv" --work "$Work" --out "$Out" --verify
```

正常生成时脚本会自行验证。退出码 `0` 表示完成并通过验证；`1` 表示生成或验证失败、不完整；`2` 表示参数、文件或翻译计划等前置条件有问题。验证主要确认译文覆盖与中文文本，不能代替对翻译质量的判断。

工作目录中较重要的文件：

| 文件 | 用途 |
|---|---|
| `segments.jsonl` | 从 PDF 提取的原始文本段 |
| `todo.json` / `skipped.jsonl` | 待译和跳过的段落 |
| `src.jsonl` | 按内容 ID 保存的中文译文 |
| `translations.jsonl` | 构建后供排版管线查询的译文表 |
| `out/` | 默认输出的 PDF 目录 |

修改译文或重新生成另一种格式时，保留并复用同一工作目录；修改 `src.jsonl` 后先重新运行 `build.py`。

## 四、将 skill 的结果添加到 Zotero

生成 PDF 只会写入指定输出目录，**不会自动创建 Zotero 附件**。希望 Codex 添加时，请在请求中明确说“添加到 Zotero 的原论文条目”；添加完成后应以 Zotero 中实际出现的附件为准。

也可以手动导入：在 Zotero 中找到并展开原论文条目，将输出目录中的 `*.mono.pdf`、`*.dual.pdf` 拖到该论文条目上，或使用 Zotero 的添加附件功能选择文件。导入后可在附件信息中修改标题，例如：

| 格式 | 建议的 Zotero 附件标题 |
|---|---|
| 纯中文 | `论文短标题-纯中文（mono）` |
| 左右双栏 | `论文短标题-双栏中英对照（dual）` |
| 逐页交替 | `论文短标题-逐页中英对照（dual）` |

Zotero 中的附件标题与磁盘文件名是两个字段。论文没有短标题时，可以直接使用格式名称。

若 PDF 已导入但标题不易识别，可在 Zotero 选中译文附件或其父条目，打开 **工具 → 开发者 → Run JavaScript**，勾选“作为异步函数执行”，粘贴 [zotero_titles.js](.dsh/skills/pdf-paper-translate/scripts/zotero_titles.js) 的内容并运行。该脚本只修改已存在附件的标题，不负责导入 PDF；对未标记布局的 `.dual.pdf` 默认按左右双栏命名。

## 五、使用 Zotero 插件右键翻译

这种方式使用插件所选的翻译服务，不会自动使用 Codex 对话中生成的译文。

1. 在 Zotero 的 **工具 → 插件** 中安装项目提供的 XPI，例如 [zotero-pdf-2-zh-v4.1.7.xpi](zotero-pdf-2-zh-v4.1.7.xpi)。插件未生效时重启 Zotero。
2. 双击 [server/start-pdf2zh.bat](server/start-pdf2zh.bat)。已有 `server\venv` 时选 `1`；已安装 uv、希望由 uv 管理服务端依赖时选 `2`。保持服务窗口运行，默认地址为 `http://127.0.0.1:8890`。
3. 在 Zotero 的 PDF2zh 插件设置中检查 Server 连接，选择翻译引擎和翻译服务。需要 API 的服务还须配置并启用对应的 Key、模型等信息。
4. 右键论文条目或 PDF 附件，在 PDF2zh 菜单中选择“翻译 PDF”或“双语对照”。前者使用插件设置的默认输出格式；后者生成左右对照文件。也可多选条目批量翻译。
5. 翻译结束后，在原论文条目下查看插件添加的附件。

服务端的 `server\venv` 仅用于启动 Server；插件所用的翻译引擎还需要单独的引擎环境。服务配置、远程部署和更多翻译选项见 [上游安装与使用说明](README.upstream.md#安装说明)。

## 六、与上游 Zotero 插件协作的不足和待完善项

目前可以把 skill 生成的 PDF 添加到上游插件使用的同一篇 Zotero 论文下，也可以分别使用插件的右键翻译。两者使用 `pdf2zh_next` 排版，但**插件的右键菜单还不能直接启动这套 Codex skill 流程**。

| 当前不足 | 需要完善的内容 |
|---|---|
| 右键操作不会把论文交给 Codex 翻译 | 在插件与 Server 之间加入明确的任务入口，把 PDF、论文或附件标识、输出格式等信息交给 skill 工作流程。保留现有翻译服务选项。 |
| 段落提取、Codex 翻译和 PDF 生成之间缺少自动衔接 | 建立任务调度和结果回传机制，依次完成提取、翻译、构建和排版。需先确定可用的 Codex 调用方式；当前对话不会自动监听 Zotero 任务。 |
| skill 输出后需要另行导入 Zotero | 将生成结果返回给插件，复用插件的附件导入逻辑，挂到发起任务的原论文下，并按纯中文或双栏格式设置附件标题。 |
| 插件界面无法展示 skill 的完整进度 | 对接现有任务状态，展示提取、翻译、生成、导入等阶段，以及失败原因、取消或重试结果，避免显示完成但附件实际未添加。 |
| 图内文字和参考文献的筛选仍需要人工确认 | 改善图注、图内标签和参考文献的识别。当前按文本内容查表，相同文字出现在正文和图中时无法分别处理，需要版面位置等信息才能解决。 |
| 译文表与插件服务的缓存没有统一管理 | 明确每篇论文的工作目录和译文复用方式，让纯中文版和双栏版共享同一份译文，同时避免引擎缓存覆盖新译文。 |
| 与上游不同版本插件的联动尚未验证 | 确定并验证插件与 Server 的请求、任务状态和文件返回协议；如需扩展协议，明确兼容的上游版本和安装方式。 |

预期流程是：**Zotero 右键提交任务 → Server 接收并调度 Codex 翻译 → 生成所选格式 → 插件将附件添加到原论文**。这是一项待开发功能；现有 `clitranslator` 配置和插件附件导入代码只是其中的基础，不能单独完成上述流程。

## 七、缓存与常见问题

- **纯中文版和双栏版用的是同一份译文吗？** skill 的默认生成流程使用同一份 `translations.jsonl`。重新排版时可复用它；切换格式不需要重新翻译。
- **引擎缓存会影响结果吗？** skill 的采集和生成都使用 `--ignore-cache`，跳过引擎翻译缓存的读取和写入，不会删除已有缓存。
- **翻译记忆是什么？** skill 可选地使用自身目录的 `memory.jsonl`，或由 `MT_MEMORY` 指定的文件。`memory.py merge --work "$Work"` 将已构建的译文合并到记忆；跨论文复用通常有限，同一论文重做时更有用。`build.py` 默认仍要求待译列表中的译文完整。
- **为什么 PDF 还没出现在 Zotero？** skill 生成文件与 Zotero 导入是两步；确认已明确请求添加，或按第四节手动导入。插件右键翻译则由插件负责挂附件。
- **为什么图内文字或参考文献仍是英文？** 这是默认保留规则；图注和正文应翻译。PDF 字体或版面复杂时仍可能出现排版或字符问题。
- **提示乱码、缺失或占位符不一致怎么办？** 根据 `build.py` 输出的内容 ID 回到原文和 `src.jsonl` 修正，重新构建后再生成。不要将 `�` 这样的替换字符写进译文。
- **Server 无法启动或插件连接失败怎么办？** 先确认已选择可用的启动模式、服务窗口仍在运行，以及插件中地址和端口与 Server 一致；默认端口是 `8890`。

## 相关项目

本项目基于 [Zotero PDF2zh](https://github.com/guaguastandup/zotero-pdf2zh)，并使用 [PDF2zh](https://github.com/Byaidu/PDFMathTranslate)、[PDF2zh_next](https://github.com/PDFMathTranslate-next/PDFMathTranslate-next) 和 [BabelDOC](https://github.com/funstory-ai/BabelDOC)。项目遵循原项目的 AGPL 协议。
