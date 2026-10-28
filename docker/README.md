# zotero-pdf2zh Docker 使用说明

> 如果你想使用 **pdf2zh**（而不是 **pdf2zh_next**）作为翻译引擎，请直接跳到文末章节：**“（可选）切换为 pdf2zh”**。

## 0. 先确认 Docker 就绪

```bash
docker version
docker compose version
```

> 如果显示不了 `docker compose`，你可能安装的是老版 `docker-compose`，后续命令把 `docker compose` 换成 `docker-compose` 即可。

---

## 1. 下载并解压 `docker.zip`

### Windows（CMD）

```cmd
mkdir zotero-pdf2zh_docker
cd zotero-pdf2zh_docker

REM 下载
curl -L -o docker.zip https://raw.githubusercontent.com/guaguastandup/zotero-pdf2zh/main/docker.zip

REM 解压（任选一种；如命令行解压失败，可在资源管理器中右键解压到当前目录）
powershell -Command "Expand-Archive -Path '.\docker.zip' -DestinationPath '.' -Force"
REM 或者（如果 tar 可用）
REM tar -xf docker.zip

REM 进入 docker 子目录（里面有 Dockerfile 和 docker-compose.yaml）
cd docker
```

### macOS / Linux（终端）

```bash
mkdir -p zotero-pdf2zh_docker
cd zotero-pdf2zh_docker

# 下载
curl -L -o docker.zip https://raw.githubusercontent.com/guaguastandup/zotero-pdf2zh/main/docker.zip

# 解压（任选其一）
unzip -o docker.zip -d .
# 或
# tar -xf docker.zip

# 进入 docker 子目录（里面有官方 Dockerfile 和 docker-compose.yaml）
cd docker
```

解压后的 `docker/` 目录包含：

```txt
Dockerfile
docker-compose.yaml
config/         （空文件夹，用于挂载配置）
translated/     （空文件夹，用于挂载输出）
```

---

## 2. 预拉取 `pdf2zh_next` 镜像

运行时临时拉镜像容易超时，先拉更稳。

```bash
docker pull awwaawwa/pdfmathtranslate-next:latest
```

**Docker镜像加速**

如果你（或你的组织）有可靠的镜像加速端点，可以在 Docker 里配置“registry-mirrors”，让所有 docker pull 走加速：

Docker Desktop（Win/macOS）：Settings → Docker Engine，在 JSON 中加入：

```json
{
    "registry-mirrors": ["https://<your-mirror-endpoint>"]
}
```

保存并 Restart。

Linux：编辑 /etc/docker/daemon.json：

```json
{
    "registry-mirrors": ["https://<your-mirror-endpoint>"]
}
```

然后 sudo systemctl restart docker。
官方文档示例见：registry mirrors 配置说明。[Docker Documentation](https://docs.docker.com/docker-hub/image-library/mirror/)

> 注：镜像站点通常由云厂商/公司私有仓库提供，域名会有差异；配置前请确认可用性与信任度。

---

## 3. 启动服务（在 `zotero-pdf2zh_docker/docker` 目录内）

```bash
docker compose up -d --build
```

看到类似输出即表示启动成功：

```cmd
* Running on http://127.0.0.1:8890
* Running on http://172.18.0.2:8890
```

常用命令：

```cmd
docker start zotero-pdf2zh
docker stop zotero-pdf2zh
docker logs -f zotero-pdf2zh   # 查看实时日志/排错
```

---

## （可选）切换为 `pdf2zh`

> 默认镜像是 `pdf2zh_next`。如果你只想用 **1.x** `pdf2zh`（`byaidu/pdf2zh:1.9.6`），按下述最小改动即可。

### 0）预拉取经典镜像

```bash
docker pull byaidu/pdf2zh:1.9.6
```

下面只给“改哪儿、怎么改”的最小改动，改完后重构即可。

---

## 1) 修改 Dockerfile

**A. 更换镜像变量，改为1.x**

找到：

```dockerfile
    ZOTERO_PDF2ZH_FROM_IMAGE=awwaawwa/pdfmathtranslate-next:latest
```

改为：

```dockerfile
    ZOTERO_PDF2ZH_FROM_IMAGE=byaidu/pdf2zh:1.9.6
```

**B. 删除“next 包装器”整段**

找到

```dockerfile
RUN printf '%s\n' \
  '#!/usr/bin/env bash' \
  'set -euo pipefail' \
  'img="${ZOTERO_PDF2ZH_FROM_IMAGE:-awwaawwa/pdfmathtranslate-next:latest}"' \
  'cid="$(cat /etc/hostname)"' \
  'exec docker run --rm --volumes-from "${cid}" -e TZ -e http_proxy -e https_proxy -e HF_ENDPOINT "$img" pdf2zh_next "$@"' \
  > /usr/local/bin/pdf2zh_next && chmod +x /usr/local/bin/pdf2zh_next
```

整块修改为：

```dockerfile
RUN printf '%s\n' \
  '#!/usr/bin/env bash' \
  'set -euo pipefail' \
  'img="${ZOTERO_PDF2ZH_FROM_IMAGE:-byaidu/pdf2zh:1.9.6}"' \
  'cid="$(cat /etc/hostname)"' \
  'exec docker run --rm --volumes-from "${cid}" -e TZ -e http_proxy -e https_proxy -e HF_ENDPOINT "$img" pdf2zh "$@"' \
  > /usr/local/bin/pdf2zh && chmod +x /usr/local/bin/pdf2zh
```

> 其它内容（server.zip 下载、requirements 安装、entrypoint）保持不变。

## 2) 修改 `docker-compose.yaml`

找到

```yaml
ZOTERO_PDF2ZH_FROM_IMAGE: awwaawwa/pdfmathtranslate-next:latest
```

改为：

```yaml
ZOTERO_PDF2ZH_FROM_IMAGE: byaidu/pdf2zh:1.9.6
```

如需挂字体（可选，字体文件与 `docker-compose.yaml` 同级）：

```yaml
volumes:
    - ./translated:/app/server/translated
    - ./config:/app/server/config
    - ./LXGWWenKai-Regular.ttf:/app/LXGWWenKai-Regular.ttf:ro # 可选
    - /var/run/docker.sock:/var/run/docker.sock
```

## 3) 重构启动（在 `docker` 目录）

```bash
docker compose down
docker compose up -d --build
```

常用命令：

```cmd
docker start zotero-pdf2zh
docker stop zotero-pdf2zh
docker logs -f zotero-pdf2zh   # 查看实时日志/排错
```

> 插件里把 **翻译引擎** 选成 `pdf2zh`（经典版）。

---

## 镜像使用教程

本项目在构建镜像时需要从 GitHub 下载 `server.zip`。默认使用**官方源**，如果你的网络访问 GitHub 生效较慢或失败，可按需启用以下两种镜像方式（二选一）：

- **方法 1：给原始链接加“代理前缀”**（如 `ghproxy.net`）
- **方法 2：直接把下载地址换成 jsDelivr CDN**

> 每次修改构建源后，都请重新构建：
> `docker compose build --no-cache && docker compose up -d`

### 0. 默认不改（官方源 + pip 自动回退）

- 默认使用：`https://raw.githubusercontent.com/guaguastandup/zotero-pdf2zh/main/server.zip`
- `pip` 安装依赖时：**先官方 PyPI**，失败自动回退 **USTC**。
  （无需任何改动即可工作，适合网络正常时使用。）

## 1）方法一：开启“代理前缀”镜像

**适用**：希望保留原始 `raw.githubusercontent.com` 链接，只在前面加个国内可达的**反代前缀**（例如 `https://ghproxy.net/`）。

**操作步骤**

1. 打开 `docker-compose.yml`，在 `build.args` 下**取消注释**并设置：

    ```yaml
    services:
        pdf2zh-server:
            build:
                args:
                    GITHUB_PROXY_PREFIX: "https://ghproxy.net/"
    ```

    > 你也可以换成你常用的其他前缀域名。

2. 重新构建并启动：

    ```bash
    docker compose build --no-cache
    docker compose up -d
    ```

3. 验证：构建日志中会出现：

    ```bash
    Download server from: https://ghproxy.net/https://raw.githubusercontent.com/guaguastandup/zotero-pdf2zh/main/server.zip
    ```

    说明代理前缀已生效。

> 备注：代理前缀服务通常为第三方社区反代，**稳定性与可用性请自评估**。无法访问时可更换域名或改用方法二。

### 2）方法二：改用 jsDelivr（CDN）

**适用**：公开仓库中的单个文件下载，CDN 稳定缓存，速度通常更好。

**操作步骤**

1. 打开 `docker-compose.yml`，在 `build.args` 下**改写** `SERVER_ZIP_URL`（并且确保 `GITHUB_PROXY_PREFIX` 留空或注释）：

    ```yaml
    services:
        pdf2zh-server:
            build:
                args:
                    SERVER_ZIP_URL: "https://cdn.jsdelivr.net/gh/guaguastandup/zotero-pdf2zh@main/server.zip"
                    # GITHUB_PROXY_PREFIX:  # 留空或注释
    ```

2. 重新构建并启动：

    ```bash
    docker compose build --no-cache
    docker compose up -d
    ```

3. 验证：构建日志中会出现：

    ```bash
    Download server from: https://cdn.jsdelivr.net/gh/guaguastandup/zotero-pdf2zh@main/server.zip
    ```

**可复现性建议**：将 `@main` 固定为版本 **tag** 或 **commit**，如：

```yaml
SERVER_ZIP_URL: "https://cdn.jsdelivr.net/gh/guaguastandup/zotero-pdf2zh@v3.0.0/server.zip"
# 或
SERVER_ZIP_URL: "https://cdn.jsdelivr.net/gh/guaguastandup/zotero-pdf2zh@<commit-sha>/server.zip"
```

## 常见检查与排错

- **查看最终配置是否生效**

    ```bash
    docker compose config
    ```

    确认 `build.args.SERVER_ZIP_URL` 与（如有）`GITHUB_PROXY_PREFIX` 是你期望的值。

- **构建日志中下载地址**
  会打印 `Download server from: ...`，可以直接确认是否命中代理或 jsDelivr。

- **404 / 连接超时**

    - 404：检查 URL 是否正确、tag 或 commit 是否存在；
    - 超时：尝试切换到另一种镜像方式，或更换代理前缀域名。

- **bash: not found**

    - 如果你选择**方案 A（改用 `/bin/sh`）**，不会出现；
    - 如果坚持使用 bash，请在 Dockerfile 里把 `bash` 安装上（见上面的“方案 B”）。

### 构建与启动（通用）

```bash
# 首次或修改镜像源后建议不走缓存
docker compose build --no-cache

# 后台启动
docker compose up -d

# 查看实时日志
docker compose logs -f
```

祝您使用愉快！
