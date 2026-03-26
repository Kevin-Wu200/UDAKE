import { Capacitor } from '@capacitor/core';
import { Device } from '@capacitor/device';
import { Directory, Encoding, Filesystem, type FileInfo } from '@capacitor/filesystem';

export interface TemplateFileEntry {
    name: string;
    size: number;
    ctime?: number;
    mtime: number;
    uri?: string;
}

export interface TemplateStorageInitResult {
    ready: boolean;
    path: string;
    version: number;
    mode: 'android' | 'web';
}

export interface TemplateSaveResult {
    filePath: string;
    uri?: string;
    overwritten: boolean;
}

type AndroidStorageTarget = {
    mode: 'absolute' | 'documents' | 'external-storage';
    basePath: string;
    directory?: Directory;
    displayPath: string;
};

const STORAGE_DIR_NAME = 'UDAKE_docs';
const PREFERRED_ABSOLUTE_DIR = `/storage/emulated/0/Download/${STORAGE_DIR_NAME}`;
const LEGACY_EXTERNAL_BASE = `Download/${STORAGE_DIR_NAME}`;
const DOCUMENTS_BASE = STORAGE_DIR_NAME;

export class TemplateStorageService {
    private static initialized = false;
    private static initPromise: Promise<TemplateStorageInitResult> | null = null;
    private static target: AndroidStorageTarget | null = null;
    private static androidVersion = 0;

    public static canUseNativeStorage(): boolean {
        try {
            return Capacitor.isNativePlatform() && Capacitor.getPlatform() === 'android';
        } catch {
            return false;
        }
    }

    public static async ensureInitialized(): Promise<TemplateStorageInitResult> {
        if (!this.canUseNativeStorage()) {
            return {
                ready: false,
                path: PREFERRED_ABSOLUTE_DIR,
                version: 0,
                mode: 'web'
            };
        }

        if (this.initialized && this.target) {
            return {
                ready: true,
                path: this.target.displayPath,
                version: this.androidVersion,
                mode: 'android'
            };
        }

        if (this.initPromise) {
            return this.initPromise;
        }

        this.initPromise = this.initializeAndroidStorage();
        try {
            const result = await this.initPromise;
            return result;
        } finally {
            this.initPromise = null;
        }
    }

    private static async initializeAndroidStorage(): Promise<TemplateStorageInitResult> {
        this.androidVersion = await this.getAndroidMajorVersion();
        const permissionGranted = await this.ensureStoragePermission(this.androidVersion);
        if (!permissionGranted) {
            return {
                ready: false,
                path: PREFERRED_ABSOLUTE_DIR,
                version: this.androidVersion,
                mode: 'android'
            };
        }

        const targets = this.buildStorageTargets(this.androidVersion);

        for (const target of targets) {
            if (await this.tryEnsureDirectory(target)) {
                this.target = target;
                this.initialized = true;
                return {
                    ready: true,
                    path: target.displayPath,
                    version: this.androidVersion,
                    mode: 'android'
                };
            }
        }

        return {
            ready: false,
            path: PREFERRED_ABSOLUTE_DIR,
            version: this.androidVersion,
            mode: 'android'
        };
    }

    private static async getAndroidMajorVersion(): Promise<number> {
        try {
            const info = await Device.getInfo();
            const version = parseInt((info.osVersion || '').split('.')[0], 10);
            return Number.isFinite(version) ? version : 0;
        } catch {
            return 0;
        }
    }

    private static buildStorageTargets(androidVersion: number): AndroidStorageTarget[] {
        const targets: AndroidStorageTarget[] = [
            {
                mode: 'absolute',
                basePath: PREFERRED_ABSOLUTE_DIR,
                displayPath: `${PREFERRED_ABSOLUTE_DIR}/`
            }
        ];

        if (androidVersion > 0 && androidVersion <= 10) {
            targets.push({
                mode: 'external-storage',
                basePath: LEGACY_EXTERNAL_BASE,
                directory: Directory.ExternalStorage,
                displayPath: `${PREFERRED_ABSOLUTE_DIR}/`
            });
        }

        targets.push({
            mode: 'documents',
            basePath: DOCUMENTS_BASE,
            directory: Directory.Documents,
            displayPath: `${PREFERRED_ABSOLUTE_DIR}/`
        });

        return targets;
    }

    private static async ensureStoragePermission(androidVersion: number): Promise<boolean> {
        try {
            const check = await Filesystem.checkPermissions();
            if (check.publicStorage === 'granted') {
                return true;
            }

            const request = await Filesystem.requestPermissions();
            return request.publicStorage === 'granted';
        } catch {
            // Android 11+ 通常不需要传统存储权限，交由 scoped storage 处理。
            return androidVersion >= 11;
        }
    }

    private static async tryEnsureDirectory(target: AndroidStorageTarget): Promise<boolean> {
        try {
            await Filesystem.mkdir({
                path: target.basePath,
                directory: target.directory,
                recursive: true
            });
            return true;
        } catch (error) {
            if (this.isAlreadyExistsError(error)) {
                return true;
            }

            return false;
        }
    }

    private static isAlreadyExistsError(error: unknown): boolean {
        const message = String((error as { message?: string })?.message || error || '').toLowerCase();
        return message.includes('exists') || message.includes('eexist') || message.includes('already');
    }

    private static async requireTarget(): Promise<AndroidStorageTarget> {
        const init = await this.ensureInitialized();
        if (!init.ready || !this.target) {
            throw new Error('PERMISSION_DENIED');
        }
        return this.target;
    }

    private static joinPath(basePath: string, filename: string): string {
        return `${basePath.replace(/\/+$/, '')}/${filename.replace(/^\/+/, '')}`;
    }

    public static getPreferredStoragePath(): string {
        return `${PREFERRED_ABSOLUTE_DIR}/`;
    }

    public static async getStorageSummary(): Promise<{ path: string; usedBytes: number; fileCount: number }> {
        if (!this.canUseNativeStorage()) {
            return {
                path: this.getPreferredStoragePath(),
                usedBytes: 0,
                fileCount: 0
            };
        }

        const files = await this.listTemplates();
        const usedBytes = files.reduce((sum, item) => sum + (item.size || 0), 0);
        const target = await this.requireTarget();
        return {
            path: target.displayPath,
            usedBytes,
            fileCount: files.length
        };
    }

    public static async fileExists(filename: string): Promise<boolean> {
        if (!this.canUseNativeStorage()) {
            return false;
        }

        const target = await this.requireTarget();
        const path = this.joinPath(target.basePath, filename);

        try {
            await Filesystem.stat({
                path,
                directory: target.directory
            });
            return true;
        } catch {
            return false;
        }
    }

    public static async saveTemplate(filename: string, content: string, overwrite = false): Promise<TemplateSaveResult> {
        const target = await this.requireTarget();
        const path = this.joinPath(target.basePath, filename);

        const exists = await this.fileExists(filename);
        if (exists && !overwrite) {
            throw new Error('FILE_EXISTS');
        }

        await Filesystem.writeFile({
            path,
            directory: target.directory,
            data: content,
            encoding: Encoding.UTF8,
            recursive: true
        });

        let uri: string | undefined;
        try {
            const uriResult = await Filesystem.getUri({ path, directory: target.directory });
            uri = uriResult.uri;
        } catch {
            uri = undefined;
        }

        return {
            filePath: `${target.displayPath}${filename}`,
            uri,
            overwritten: exists
        };
    }

    public static async listTemplates(): Promise<TemplateFileEntry[]> {
        if (!this.canUseNativeStorage()) {
            return [];
        }

        const target = await this.requireTarget();

        try {
            const result = await Filesystem.readdir({
                path: target.basePath,
                directory: target.directory
            });

            const files = (result.files || [])
                .filter((item: FileInfo) => item.type === 'file' && /\.(geojson|json)$/i.test(item.name))
                .sort((a: FileInfo, b: FileInfo) => (b.mtime || 0) - (a.mtime || 0))
                .map((item: FileInfo) => ({
                    name: item.name,
                    size: item.size || 0,
                    ctime: item.ctime,
                    mtime: item.mtime || 0,
                    uri: item.uri
                }));

            return files;
        } catch {
            return [];
        }
    }

    public static async deleteTemplate(filename: string): Promise<void> {
        const target = await this.requireTarget();
        const path = this.joinPath(target.basePath, filename);

        await Filesystem.deleteFile({
            path,
            directory: target.directory
        });
    }

    public static async clearTemplates(): Promise<number> {
        const files = await this.listTemplates();
        let deleted = 0;

        for (const file of files) {
            try {
                await this.deleteTemplate(file.name);
                deleted += 1;
            } catch {
                // 单个文件失败不应中断整体清理
            }
        }

        return deleted;
    }

    public static async openStorageFolder(): Promise<boolean> {
        if (typeof window !== 'undefined' && window.electronAPI && (window.electronAPI as any).openDownloadFolder) {
            (window.electronAPI as any).openDownloadFolder();
            return true;
        }

        if (!this.canUseNativeStorage()) {
            return false;
        }

        const target = await this.requireTarget();
        let uri: string | undefined;

        try {
            const result = await Filesystem.getUri({
                path: target.basePath,
                directory: target.directory
            });
            uri = result.uri;
        } catch {
            uri = undefined;
        }

        if (!uri) {
            return false;
        }

        window.open(uri, '_system') || window.open(uri, '_blank');
        return true;
    }

    public static async openTemplateFile(filenameOrPath: string): Promise<boolean> {
        if (!filenameOrPath) {
            return false;
        }

        if (!this.canUseNativeStorage()) {
            return false;
        }

        const target = await this.requireTarget();
        const filename = filenameOrPath.split('/').pop() || filenameOrPath;
        const path = this.joinPath(target.basePath, filename);

        try {
            const result = await Filesystem.getUri({
                path,
                directory: target.directory
            });
            window.open(result.uri, '_system') || window.open(result.uri, '_blank');
            return true;
        } catch {
            return false;
        }
    }
}
