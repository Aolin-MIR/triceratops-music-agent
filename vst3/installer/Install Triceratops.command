#!/bin/bash
set -u
root="$(cd -- "$(dirname -- "$0")" && pwd)"
echo 'Triceratops 1.0.2 · Mac online installer / 联网安装'
echo 'Save and quit REAPER / Logic Pro before updating. 请先保存并退出宿主。'
export TRICERATOPS_DOWNLOAD_SOURCE="${TRICERATOPS_DOWNLOAD_SOURCE:-auto}"
echo 'Automatic download selection; verified alternate sources are retried on failure.'
echo '自动选择下载源，失败后切换备用源，校验通过才会安装。'
/bin/bash "$root/setup-macos.sh"
result=$?
if [[ "$result" != 0 ]]; then echo 'Installation failed; see the error above. 安装失败，请保留上方错误信息后重试。'; fi
read -r -p 'Press Return to close / 按回车关闭。' ignored
exit "$result"
