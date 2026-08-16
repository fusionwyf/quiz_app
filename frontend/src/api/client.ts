// axios 实例：统一 baseURL 与错误处理
import axios, { AxiosError } from 'axios';
import { message } from 'antd';

declare module 'axios' {
  export interface AxiosRequestConfig {
    /** 为 true 时请求失败不弹提示（由调用方自行处理） */
    silent?: boolean;
  }
}

// 桌面打包模式：Tauri 在页面脚本执行前注入 window.__BACKEND_PORT__（后端实际端口）
const backendPort = (window as unknown as { __BACKEND_PORT__?: number })
  .__BACKEND_PORT__;

export const API_BASE = backendPort
  ? `http://127.0.0.1:${backendPort}`
  : import.meta.env.VITE_API_BASE || 'http://localhost:8000';

export const client = axios.create({
  baseURL: API_BASE,
  timeout: 30000,
});

client.interceptors.response.use(
  (resp) => resp,
  (error: AxiosError<{ detail?: string }>) => {
    // 主动取消的请求（如组件卸载/重复加载）不提示
    if (axios.isCancel(error)) {
      return Promise.reject(error);
    }
    // 调用方标记 silent 时不弹提示
    if (error.config?.silent) {
      return Promise.reject(error);
    }
    const detail = error.response?.data?.detail;
    const text =
      typeof detail === 'string' && detail
        ? detail
        : error.message || '请求失败';
    message.error(text);
    return Promise.reject(error);
  },
);
