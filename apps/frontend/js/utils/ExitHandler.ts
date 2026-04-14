import { AppExitHandler } from './AppExitHandler.js';

export class ExitHandler {
    public static async exitProgram(): Promise<void> {
        const exitedNative = await AppExitHandler.tryExitApp();
        if (exitedNative) {
            return;
        }

        try {
            window.close();
        } catch {
            // 忽略浏览器阻止关闭的异常
        }

        window.alert('当前环境不允许脚本直接关闭页面，请手动关闭此标签页。');
    }
}
