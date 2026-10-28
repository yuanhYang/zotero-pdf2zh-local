<div align="center">

![Zotero PDF2zh](./addon/content/icons/favicon@0.5x.svg)

[![zotero target version](https://img.shields.io/badge/Zotero-7-green?style=flat-square&logo=zotero&logoColor=CC2936)](https://www.zotero.org)
[![Using Zotero Plugin Template](https://img.shields.io/badge/Using-Zotero%20Plugin%20Template-blue?style=flat-square&logo=github)](https://github.com/windingwind/zotero-plugin-template)
![Downloads release](https://img.shields.io/github/downloads/guaguastandup/zotero-pdf2zh/total?color=yellow)
[![License](https://img.shields.io/github/license/guaguastandup/zotero-pdf2zh)](https://github.com/guaguastandup/zotero-pdf2zh/blob/main/LICENSE)

在Zotero中使用[PDF2zh](https://github.com/Byaidu/PDFMathTranslate)和[PDF2zh_next](https://github.com/PDFMathTranslate/PDFMathTranslate-next)

[使用pdf2zh教程(Stable)](./README.md) | [使用pdf2zh_next教程(本页面, Experimental)](./README_babeldoc.md)

</div>

# 如何使用本插件

本指南将引导您完成 Zotero PDF2zh 插件的安装和配置。

遇到问题：

- 请先访问：[常见问题](https://github.com/guaguastandup/zotero-pdf2zh/issues/64)
- 尝试问一下AI
- 提issue或到插件群发自己的终端报错截图（一定要有终端截图，谢谢！）

## 方法一：uv安装

**第一步：创建目录，存放本插件需要的所有文件**

```shell
# 1. 创建并进入zotero-pdf2zh文件夹
mkdir zotero-pdf2zh-next && cd zotero-pdf2zh-next
# 2. 下载server.py文件
wget https://raw.githubusercontent.com/guaguastandup/zotero-pdf2zh/refs/heads/main/server.py
# 3. 创建translated文件夹，存放翻译输出文件
mkdir translated
```

文件夹结构如下：

```shell
zotero-pdf2zh-next
    ├── config.toml
    ├── server.py
    └── translated
```

**第二步：安装pdf2zh_next**

1. [**Windows EXE**](https://pdf2zh-next.com/getting-started/INSTALLATION_winexe.html) <small>Recommand for Windows</small>

2. [**Docker**](https://pdf2zh-next.com/getting-started/INSTALLATION_docker.html) <small>Recommand for Linux</small>

3. [**uv** (a Python package manager)](https://pdf2zh-next.com/getting-started/INSTALLATION_uv.html) <small>Recommand for macOS</small>

**uv安装**

进入`zotero-pdf2zh-next`文件夹：

1.  安装uv环境

```shell
# 方法一: 使用pip安装uv
pip install uv
# 方法二: 下载脚本安装
# macOS/Linux
wget -qO- https://astral.sh/uv/install.sh | sh
# windows
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

2.  uv安装Python 3.12

```shell
uv python install 3.12  # 安装3.12版本python
uv venv --python 3.12   # 创建3.12版本python虚拟环境
```

3.  启动虚拟环境

- Linux/macOS执行

    ```shell
    source .venv/bin/activate
    ```

- windows执行

    ```shell
    .\.venv\Scripts\activate
    ```

3.  第三步: 安装需要的包

    ```shell
    uv pip install pdf2zh_next pypdf flask
    ```

**第三步: 测试安装并启动gui**

1. 在命令行输入`pdf2zh_next --gui`进入图形界面。

2. 在图形界面中选择一个本地PDF进行翻译，按照[翻译服务文档](https://pdf2zh-next.com/zh/advanced/Documentation-of-Translation-Services.html)和[高级选项文档](https://pdf2zh-next.com/zh/advanced/advanced.html)完成配置，进行翻译。

3. 翻译成功后，退出图形界面

在第一步创建的`zotero-pdf2zh-next`文件路径中, 在命令行执行：

MacOS/Linux

```shell
cp ~/.config/pdf2zh/config.v3.toml ./config.toml
```

Windows(cmd)

```shell
copy "%USERPROFILE%\.config\pdf2zh\config.v3.toml" config.toml
```

Windows (PowerShell)

```shell
Copy-Item "$env:USERPROFILE\.config\pdf2zh\config.v3.toml" -Destination "config.toml"
```

- 本步骤创建的`config.toml`可用于未来配置其他LLM服务和翻译选项。

**第四步: zotero插件设置**

打开zotero-pdf2zh插件设置

- 将翻译引擎选择为: `pdf2zh_next`
- 将配置文件路径改为: `./config.toml`

可配置字段:

- 翻译服务
- 线程数 (对应pdf2zh_next里的qps)
- 翻译文件输出路径
- 配置文件路径(格式为toml)
- 跳过最后几页不翻译
- 重命名条目为短标题
- 默认生成文件(不支持生成双语对照文件-单栏PDF)

各字段功能请参考[PDF2zh教程](./README.md)

## 方法二：docker安装

### 第一步：创建目录，存放本插件需要的所有文件

```shell
# 1. 创建并进入zotero-pdf2zh文件夹
mkdir zotero-pdf2zh-next && cd zotero-pdf2zh-next
# 2. 从 zotero-pdf2zh 官方 GitHub 仓库下载配置文件
#    - Dockerfile: 定义了如何构建我们服务的镜像
#    - docker-compose.yaml: 定义了如何运行和编排我们的服务
curl -o Dockerfile https://raw.githubusercontent.com/guaguastandup/zotero-pdf2zh/main/Dockerfile
curl -o docker-compose.yaml https://raw.githubusercontent.com/guaguastandup/zotero-pdf2zh/main/docker-compose.yaml

# 3. 创建一个子目录，专门用于存放需要持久化的数据
#    这包括你的个人配置和翻译后的文件
mkdir zotero-pdf2zh && cd zotero-pdf2zh

# 4. 在数据目录内，预先创建用于存放翻译结果的文件夹
mkdir translated

# 5. 操作完成后，返回到项目根目录，为下一步做准备
cd ..
```

### 第二步：修改docker-compose.yaml

原仓库默认使用 `byaidu/pdf2zh:1.9.6`，版本老、依赖旧。**直接换成社区更活跃的 `awwaawwa/pdfmathtranslate-next:latest`**，就能原地升级到 2.x 新引擎，并内置 `pdf2zh_next`（不再需要自己 `pip install`）。

请用以下内容**完全覆盖**你下载的 `docker-compose.yaml` 文件：

```yaml
services:
    zotero-pdf2zh:
        build:
            context: .
            dockerfile: Dockerfile
            args:
                # 我们在这里指定了构建时使用的基础镜像。
                # 相比原始的 byaidu/pdf2zh，awwaawwa/pdfmathtranslate-next 更新更频繁，功能更强。
                - ZOTERO_PDF2ZH_FROM_IMAGE=awwaawwa/pdfmathtranslate-next:latest
                - ZOTERO_PDF2ZH_SERVER_FILE_DOWNLOAD_URL=https://raw.githubusercontent.com/guaguastandup/zotero-pdf2zh/refs/heads/main/server.py
        container_name: zotero-pdf2zh
        # restart: unless-stopped 是一条黄金法则，
        # 它能确保 Docker 服务在宿主机重启后自动恢复，实现“开机自启”。
        restart: unless-stopped
        ports:
            - "8888:8888" # 将容器的 8888 端口映射到你电脑的 8888 端口
        environment:
            - TZ=Asia/Shanghai # 设置时区，确保日志时间正确
            - HF_ENDPOINT=https://hf-mirror.com # 使用 HuggingFace 镜像，加速模型下载
        volumes:
            # 将我们创建的本地目录映射到容器内部
            - ./zotero-pdf2zh/translated:/app/translated # 挂载翻译结果目录
            - ./zotero-pdf2zh/config.toml:/app/config.toml # 核心！Zotero 读取的新版 TOML 配置文件 2.x 配置文件
```

---

### 第三步：生成 config.toml

1. **先跑一次** PDFMathTranslate-next 桌面版或 Web UI，把 OpenAI／DeepL Key、目标语言、并发数等都配好。
2. 系统会生成 `config.v3.toml` （路径见下表）。复制并改名成 `config.toml` 放到 `zotero-pdf2zh/` 目录下即可。

```bash
# Windows (cmd)
copy "%USERPROFILE%\.config\pdf2zh\config.v3.toml" zotero-pdf2zh\config.toml
# PowerShell
Copy-Item "$env:USERPROFILE\.config\pdf2zh\config.v3.toml" zotero-pdf2zh\config.toml
# macOS / Linux
cp ~/.config/pdf2zh/config.v3.toml zotero-pdf2zh/config.toml
```

操作完毕后，你的最终目录结构应如下所示：

```Plaintext
zotero-pdf2zh-docker/
├── Dockerfile
├── docker-compose.yaml
└── zotero-pdf2zh/
    ├── config.toml      <-- 你的 API Key 和配置在这里
    └── translated/      <-- 翻译后的文件将出现在这里
```

### 第四步： 一键启动与日常管理

现在，万事俱备。让我们启动服务。

#### **首次部署**

在项目根目录下（即 `docker-compose.yaml` 所在的位置）执行：

```bash
# 推荐：先清理可能存在的同名旧容器，避免冲突 (|| true 会忽略容器不存在的错误)
docker rm -f zotero-pdf2zh || true

# 一键构建镜像并在后台启动服务
# --build: 强制根据 Dockerfile 重新构建镜像，以应用我们的修改
# -d:      detached 模式，让服务在后台安静运行
docker-compose up -d --build
```

> 重启电脑后，因设置了 `restart: unless-stopped`，容器会自动拉起；若未生效，手动 `docker start zotero-pdf2zh` 即可。

### 第五步：zotero插件设置

打开zotero-pdf2zh插件设置

- 将翻译引擎选择为: `pdf2zh_next`
- 将配置文件路径改为: `./config.toml`

可配置字段:

- 翻译服务
- 线程数 (对应pdf2zh_next里的qps)
- 翻译文件输出路径
- 配置文件路径(格式为toml)
- 跳过最后几页不翻译
- 重命名条目为短标题
- 默认生成文件(不支持生成双语对照文件-单栏PDF)

各字段功能请参考[PDF2zh教程](./README.md)
