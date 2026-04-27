import { AppExitHandler } from './AppExitHandler.js';
import { I18n } from './I18n.js';

const t = (key: string, params?: Record<string, string | number>): string => I18n.t(key, params);

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

        window.alert(t('error.exit.failed'));
    }
}
