// 题库文件导入弹窗：拖拽上传 txt / md / docx，展示导入结果
import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Alert,
  Button,
  Checkbox,
  List,
  Modal,
  Space,
  Statistic,
  Tooltip,
  Typography,
  Upload,
  message,
} from 'antd';
import { InboxOutlined } from '@ant-design/icons';
import type { UploadFile } from 'antd';
import { theme } from 'antd';
import { getLlmStatus, importQuestionsFile } from '../api';
import { queryKeys } from '../api/queries';
import type { ImportResult } from '../api/types';
import LlmSettingsForm from './LlmSettingsForm';

const { Dragger } = Upload;
const { Text } = Typography;

const ACCEPT = '.txt,.md,.markdown,.docx';
const MAX_SIZE_MB = 10;

interface ImportModalProps {
  open: boolean;
  bankId: number;
  bankName: string;
  onClose: () => void;
}

export default function ImportModal({
  open,
  bankId,
  bankName,
  onClose,
}: ImportModalProps) {
  const qc = useQueryClient();
  const { token } = theme.useToken();
  const [fileList, setFileList] = useState<UploadFile[]>([]);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [forceLlm, setForceLlm] = useState(false);
  const [configOpen, setConfigOpen] = useState(false);

  // 弹窗打开时查询 LLM 智能整理状态（失败静默）
  const { data: llmStatus } = useQuery({
    queryKey: queryKeys.llmStatus,
    queryFn: getLlmStatus,
    enabled: open,
  });

  const importMutation = useMutation({
    mutationFn: (file: File) => importQuestionsFile(bankId, file, forceLlm),
    onSuccess: (res) => {
      setResult(res);
      // 无论导入几题（含全部判重跳过）都刷新列表缓存，防止计数过期
      qc.invalidateQueries({ queryKey: queryKeys.banks });
      qc.invalidateQueries({ queryKey: ['questions'] });
    },
  });

  const handleClose = () => {
    setFileList([]);
    setResult(null);
    setForceLlm(false);
    onClose();
  };

  const handleImport = () => {
    const raw = fileList[0]?.originFileObj;
    if (!raw) {
      message.warning('请先选择文件');
      return;
    }
    importMutation.mutate(raw as File);
  };

  return (
    <Modal
      title={`导入题目到「${bankName}」`}
      open={open}
      onCancel={handleClose}
      width={560}
      footer={
        result ? (
          // 导入完成（含成功/部分失败）后只保留关闭，避免误点再次导入造成重复
          <Button onClick={handleClose}>关闭</Button>
        ) : (
          <Space>
            <Button onClick={handleClose}>关闭</Button>
            <Button
              type="primary"
              loading={importMutation.isPending}
              disabled={fileList.length === 0}
              onClick={handleImport}
            >
              开始导入
            </Button>
          </Space>
        )
      }
    >
      {!result ? (
        <>
          {llmStatus?.enabled ? (
            <Alert
              type="info"
              showIcon
              style={{ marginBottom: 12 }}
              message={`已启用 AI 智能整理（${llmStatus.model}）：解析失败时自动兜底`}
            />
          ) : (
            <Alert
              type="warning"
              showIcon
              style={{ marginBottom: 12 }}
              message="未配置 AI 智能整理"
              description="配置 OpenAI 兼容 API 后，格式混乱的文件可由 AI 自动整理成标准格式再解析。"
              action={
                <Button size="small" onClick={() => setConfigOpen(true)}>
                  配置
                </Button>
              }
            />
          )}
          <Dragger
            accept={ACCEPT}
            maxCount={1}
            fileList={fileList}
            beforeUpload={(file) => {
              const okSize = file.size <= MAX_SIZE_MB * 1024 * 1024;
              if (!okSize) {
                message.error(`文件大小不能超过 ${MAX_SIZE_MB}MB`);
                return Upload.LIST_IGNORE;
              }
              setFileList([
                { uid: file.uid ?? '-1', name: file.name, originFileObj: file },
              ]);
              return false; // 手动上传
            }}
            onRemove={() => setFileList([])}
          >
            <p className="ant-upload-drag-icon">
              <InboxOutlined />
            </p>
            <p className="ant-upload-text">点击或拖拽文件到此区域</p>
            <p className="ant-upload-hint">
              支持 .txt / .md / .docx，最大 {MAX_SIZE_MB}MB；内容兼容键值格式
              （题目：/类型：/选项：/答案：）与通用试卷格式（1. 题干 / A. 选项 /
              答案：B）
            </p>
          </Dragger>
          <div style={{ marginTop: 12 }}>
            <Tooltip title="忽略直接解析结果，文件内容全部经 AI 重新整理为标准格式（适合格式混乱、可能被解析出错误题目的文件）。长文件自动分块，耗时随文件大小增加。">
              <Checkbox
                checked={forceLlm}
                disabled={!llmStatus?.enabled}
                onChange={(e) => setForceLlm(e.target.checked)}
              >
                强制 AI 整理
              </Checkbox>
            </Tooltip>
          </div>
        </>
      ) : (
        <Space direction="vertical" style={{ width: '100%' }} size="middle">
          <Space size="large">
            <Statistic title="成功导入" value={result.imported_count} />
            <Statistic
              title="跳过"
              value={result.skipped_count}
              valueStyle={
                result.skipped_count > 0 ? { color: token.colorWarning } : undefined
              }
            />
          </Space>
          {result.errors.length > 0 && (
            <Alert
              type="warning"
              showIcon
              message={
                result.truncated
                  ? '以下仅显示部分错误明细：'
                  : '以下题目未导入：'
              }
              description={
                <List
                  size="small"
                  dataSource={result.errors}
                  renderItem={(item) => <List.Item>{item}</List.Item>}
                />
              }
            />
          )}
          {result.ai_normalized && (
            <Alert
              type="info"
              showIcon
              message="本次导入由 AI 智能整理完成（原文件格式无法直接解析）"
            />
          )}
          {(result.duplicate_count ?? 0) > 0 && (
            <Alert
              type="info"
              showIcon
              message={`其中 ${result.duplicate_count} 题与库内已有题目重复，已自动跳过`}
            />
          )}
          {result.ai_error && (
            <Alert type="warning" showIcon message={result.ai_error} />
          )}
          {result.skipped_count === 0 && !result.ai_error && (
            <Text type="success">全部题目导入成功</Text>
          )}
        </Space>
      )}
      <Modal
        title="配置 AI 智能整理"
        open={configOpen}
        footer={null}
        onCancel={() => setConfigOpen(false)}
        width={520}
        destroyOnClose
      >
        <LlmSettingsForm
          onSaved={() => {
            setConfigOpen(false);
            qc.invalidateQueries({ queryKey: queryKeys.llmStatus });
          }}
        />
      </Modal>
    </Modal>
  );
}

