/**
 * StateManager 与 Store 的桥接器
 * 解决状态分散与重复维护问题
 */

import { StateManager } from '../managers/StateManager';
import { appStore } from './Store';
import { Logger } from '../utils/Logger';

export interface StateBridge {
    start(): void;
    stop(): void;
}

const DEFAULT_KEY_MAP: Record<string, string> = {
    currentTheme: 'theme.current',
    currentLanguage: 'i18n.locale',
    currentProjectId: 'project.id',
    currentTaskId: 'taskId'
};

export function createStateBridge(
    stateManager: StateManager,
    keyMap: Record<string, string> = DEFAULT_KEY_MAP
): StateBridge {
    let started = false;
    let syncingFromStateManager = false;
    let syncingFromStore = false;
    const unsubscribers: Array<() => void> = [];

    const start = () => {
        if (started) {
            return;
        }

        started = true;

        Object.entries(keyMap).forEach(([stateKey, storeKey]) => {
            const unsubscribeState = stateManager.subscribe(stateKey, (newValue) => {
                if (syncingFromStore) {
                    return;
                }
                syncingFromStateManager = true;
                try {
                    appStore.set(storeKey, newValue);
                } finally {
                    syncingFromStateManager = false;
                }
            });

            const unsubscribeStore = appStore.subscribe(storeKey, (newValue) => {
                if (syncingFromStateManager) {
                    return;
                }
                syncingFromStore = true;
                try {
                    stateManager.setState(stateKey, newValue);
                } finally {
                    syncingFromStore = false;
                }
            });

            unsubscribers.push(unsubscribeState);
            unsubscribers.push(unsubscribeStore);

            // 初始化时从 StateManager 同步一次到 Store
            if (stateManager.hasState(stateKey)) {
                appStore.set(storeKey, stateManager.getState(stateKey));
            }
        });

        Logger.info('StateBridge', '状态桥接已启动');
    };

    const stop = () => {
        while (unsubscribers.length > 0) {
            const unsubscribe = unsubscribers.pop();
            unsubscribe?.();
        }
        started = false;
        Logger.info('StateBridge', '状态桥接已停止');
    };

    return {
        start,
        stop
    };
}
