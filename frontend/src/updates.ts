// 桌面端更新逻辑共享模块：页头自动检查与设置页手动检查共用
export const RELEASES_URL = 'https://github.com/fusionwyf/quiz_app/releases';
export const REPO_URL = 'https://github.com/fusionwyf/quiz_app';
export const ISSUES_URL = 'https://github.com/fusionwyf/quiz_app/issues';

export function isDesktopApp(): boolean {
  return typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window;
}

export interface AppUpdate {
  version: string;
  notes?: string;
  downloadAndRestart: () => Promise<void>;
}

/** 检查更新；无更新返回 null，非桌面环境/网络失败抛异常由调用方处理 */
export async function checkForUpdate(): Promise<AppUpdate | null> {
  const { check } = await import('@tauri-apps/plugin-updater');
  const update = await check();
  if (!update) return null;
  return {
    version: update.version,
    notes: update.body ?? undefined,
    downloadAndRestart: async () => {
      await update.downloadAndInstall();
      const { relaunch } = await import('@tauri-apps/plugin-process');
      await relaunch();
    },
  };
}

/** 当前应用版本（桌面端读 Tauri，浏览器开发模式返回 dev） */
export async function getAppVersion(): Promise<string> {
  if (isDesktopApp()) {
    const { getVersion } = await import('@tauri-apps/api/app');
    return getVersion();
  }
  return 'dev';
}
