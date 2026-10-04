# WebChat 扩展插件
家装平台Web网页聊天客户端扩展，**不修改平台原有任何源码**。

## 访问地址
- 聊天页面：`http://127.0.0.1:8000/ext-webchat/chat.html`
- 接口：`POST /ext-webchat/api/chat`

## 启动方式
使用 `start_with_webchat.ps1` 启动，原生平台启动脚本不会加载此插件。

## 功能
- 移动端自适应聊天界面，打字机动画、加载动画、清空会话
- 对接平台内部Lead获客Agent，复用memory记忆与SQLite线索存储
