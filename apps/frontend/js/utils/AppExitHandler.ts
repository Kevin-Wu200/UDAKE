export class AppExitHandler {
    public static async tryExitApp(): Promise<boolean> {
        const win = window as unknown as {
            Capacitor?: {
                Plugins?: {
                    App?: {
                        exitApp?: () => Promise<void> | void;
                    };
                };
            };
        };
        const appPlugin = win.Capacitor?.Plugins?.App;
        if (!appPlugin || typeof appPlugin.exitApp !== 'function') {
            return false;
        }
        try {
            await appPlugin.exitApp();
            return true;
        } catch {
            return false;
        }
    }
}
