# Basis Desktop (ADR 0004)

开发：仓库根目录或本目录 `npm run dev`（API + Vite :3001 + Electron）。

打包对齐 Fellow `@fellow/desktop`：`build:desktop` → `stage:api` → `verify:release-resources` → `electron-builder`。

## 日常

```bash
cd desktop && npm install && npm run dev
```

不要在 `web/` 单独跑 `dev:desktop` 指望出现 Electron——那只是 Vite。

已安装的 Basis 与 `npm run dev` **不要同时开**：两者共用 `~/.basis/basis.db`，第二个 API 可能起不来。开发时用 dev；测安装包前先退出 dev。

若 Release 安装包启动失败并提示 **workspaces / knowledge_bases**：本机 `~/.basis/basis.db` 可能是旧版 schema。备份后删除 `~/.basis/basis.db`（或整个 `~/.basis`），再打开应用会重建空库。

应用图标：`npm run icons` 用与 sidebar `AppLogo` 相同的 `thinking-orbs` 预设（`working`、20px、浅色主题、静态帧）渲染到 `build/icon.*`；打包脚本会自动跑。

## 打包（macOS）

```bash
cd desktop && npm install
npm run dist:mac:unsigned   # .dmg + .zip（未签名；默认内嵌 Python sidecar）
# 等价于 Fellow 的 dist:mac:unsigned
```

## 打包（Windows）

在 **Windows** 上执行（`stage:api` 内嵌的 Python venv 与当前 OS/架构绑定，不能在 mac 上打出可运行的 Win sidecar）：

```bash
cd desktop && npm install
npm run dist:win:unsigned   # NSIS 安装包 + portable（未签名）
```

产物示例：`release/Basis-0.1.0-win32-x64.exe`、`release/Basis-0.1.0-win32-x64.exe`（portable 同名规则见 electron-builder 输出）。

发布默认 **`stage:api` 会 bundle** `.api-stage/sidecar`（运行时不需要 git checkout / `uv`）。仅本机快速试打小包：

```bash
node scripts/stage-api.mjs --uv-monorepo
```

Web 静态资源来自 `dist/web`（`web` 的 `build:desktop`），不再复制到 `desktop/pack/`。

打包后可选验证：

```bash
npm run smoke:api
```

单测：`npm run test`（`static-server`、release 资源校验、sidebar orb 渲染）。

Web Desktop 产品 e2e（CI `e2e-desktop`）：在 `web/` 下  
`cd tests/e2e && npm ci && BASIS_E2E_DESKTOP=1 CI=1 npm test desktop-product.e2e.spec.ts`

## Profile

`profiles/profile.desktop.yaml` — API `server.port: 0`；数据 `~/.basis`；桌面 `auth.enabled: false`。

## CI 发布（GitHub Release，与 Docker 分开）

| 类型 | Tag | Workflow |
|------|-----|----------|
| 容器 | `v0.1.0` | [`.github/workflows/release-docker.yml`](../.github/workflows/release-docker.yml) |
| 桌面 | `desktop-v0.1.0` | [`.github/workflows/release-desktop.yml`](../.github/workflows/release-desktop.yml) |

```bash
git tag desktop-v0.1.0
git push origin desktop-v0.1.0
```

在 **macOS** / **Windows** runner 上各打一份 **未签名** 安装包（`.dmg`/`.zip`、NSIS/portable），并写入 **Draft** Release **Basis desktop-v0.1.0 (Desktop)**。在 [Releases](https://github.com/coldbuffer/basis/releases) 列表点 **Desktop** 草稿（不要和 **Docker** 草稿搞混；Docker 无安装包附件）。Apple Silicon 用 `Basis-*-darwin-arm64.dmg`。验证后点 **Publish release**。

**Not yet:** 签名 / notarize、Authenticode、Linux AppImage/deb。

桌面壳启动后会查 GitHub `desktop-v*` Release；若有新版本，顶栏下出现提示条，点击在浏览器打开对应 Release 页（非自动下载安装）。

**macOS 从浏览器安装（未签名）：**

1. 先把 `.dmg` 拖进 **应用程序**，不要长期从磁盘映像里直接双击 `.app`。
2. 若提示 *damaged* / 无法打开，在终端执行（路径按你的下载位置改）：

```bash
xattr -dr com.apple.quarantine ~/Downloads/Basis-*-darwin-arm64.dmg
# 已装进应用程序后：
xattr -cr "/Applications/Basis.app"
codesign --force --deep --sign - "/Applications/Basis.app"
open -a "/Applications/Basis.app"
```

也可 **右键 Basis.app → 打开** 第一次绕过 Gatekeeper。

**`spawn …/sidecar/venv/bin/basis ENOENT`：** 旧 CI 包内嵌了 python.org 的 Python（指向 `/Library/Frameworks/...`），换机器后无法启动。请安装 **修复打包后的** 新 `desktop-v*` Release（sidecar 使用 uv managed Python + afterPack relocate）。
