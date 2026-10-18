# 静态签名器（可选）

这个目录是 `StaticSigner` 的默认落点：`<data>/signer/sign.js`。

## 现在需要它吗

**不需要。** 默认 `DOUYIN_SIGNER=browser`，签名由真实页面实时生成，页面更新后自动跟着变。

只有当你需要在**完全没有浏览器**的环境里签名时，才启用它。

## 怎么启用

1. 从当前页面的 `runtime~client-entry.*.js` 里把 `frontierSign` 相关代码抽成一个独立脚本，导出为命令行形式：

```js
// sign.js —— 入参 argv[2] 是完整 URL，stdout 输出 X-Bogus
const token = frontierSign({ url: process.argv[2] })["X-Bogus"];
process.stdout.write(token);
```

2. 放到本目录，命名 `sign.js`
3. 启动时设置：

```powershell
$env:DOUYIN_SIGNER = "static"
$env:DOUYIN_SIGNER_BUNDLE = "<绝对路径>\signer\sign.js"
```

## 验证

```powershell
node sign.js "https://www.douyin.com/aweme/v1/web/hot/search/list/?aid=6383"
# 应输出 16 字符
```

## 风险

静态包会随抖音发布而失效。一旦 bundle 更新，`frontierSign` 的内部实现（环境指纹、随机种子、加密表）可能全变，你需要重新抽取。

`SignerRegistry` 的链式回退会处理这种情况：browser 失败时自动落到 static，两个都失败才报 `SIGN_FAILED`，并且错误信息里带上每一环的具体原因。

## 注意

不要把这个目录里的任何东西提交到公开仓库——抽取出来的代码属于对方的实现。
