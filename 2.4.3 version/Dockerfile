ARG ZOTERO_PDF2ZH_FROM_IMAGE
FROM ${ZOTERO_PDF2ZH_FROM_IMAGE}

ARG ZOTERO_PDF2ZH_SERVER_FILE_DOWNLOAD_URL

WORKDIR /app

# 如果国内环境打包取消注释，使用镜像
# RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources && \
#    sed -i 's/security.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources

RUN apt-get update && \
    # 调试网络用工具
    #    apt-get -y install iproute2 curl vim iputils-ping procps net-tools traceroute dnsutils && \
    # 如果国内环境打包取消注释，使用镜像
    #    pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple && \
    #    pip config set global.extra-index-url "https://pypi.tuna.tsinghua.edu.cn/simple" && \
    uv pip install --system -U flask waitress pypdf

ADD "${ZOTERO_PDF2ZH_SERVER_FILE_DOWNLOAD_URL}" /app/
# fix bug in server.py for run in Linux
RUN sed -i '/path = path\.replace/ s/ #//' /app/server.py

EXPOSE 8888
CMD ["python", "server.py", "8888"]
