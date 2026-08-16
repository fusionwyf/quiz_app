// 首次引导弹层：三步指引 + 一键导入示例题库（spec P3）
// 「已完成引导」记在浏览器 localStorage——引导是设备级提示，不属于用户数据
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Button, Modal, Space, Steps, Typography, message } from 'antd';
import { useNavigate } from 'react-router-dom';
import { useState } from 'react';
import { importSampleBank } from '../api';
import { queryKeys } from '../api/queries';

const STORAGE_KEY = 'quiz-onboarding-done';

export function shouldShowOnboarding(): boolean {
    return localStorage.getItem(STORAGE_KEY) !== '1';
}

export default function OnboardingModal({ onClose }: { onClose: () => void }) {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [step, setStep] = useState(0);

  const finish = () => {
    localStorage.setItem(STORAGE_KEY, '1');
    onClose();
  };

  const sampleMutation = useMutation({
    mutationFn: importSampleBank,
    onSuccess: () => {
      message.success('示例题库已导入，去开一局试试吧');
      qc.invalidateQueries({ queryKey: queryKeys.banks });
      finish();
      navigate('/quiz/start');
    },
  });

  return (
    <Modal
      title="欢迎使用刷题助手"
      open
      onCancel={finish}
      width={560}
      footer={
        <Space>
          <Button onClick={finish}>跳过，我自己导入</Button>
          {step < 2 ? (
            <Button type="primary" onClick={() => setStep(step + 1)}>
              下一步
            </Button>
          ) : (
            <Button
              type="primary"
              loading={sampleMutation.isPending}
              onClick={() => sampleMutation.mutate()}
            >
              导入示例题库
            </Button>
          )}
        </Space>
      }
    >
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <Steps
          current={step}
          items={[
            { title: '导入题库', description: '新建题库后上传 txt/md/docx 文件' },
            { title: '开始练习', description: '顺序 / 随机 / 错题三种开局' },
            { title: '错题本', description: '答错自动记录，连对自动出本' },
          ]}
        />
        {step === 0 && (
          <Typography.Paragraph>
            把你的复习资料整理成题库文件导入：支持「题目：/类型：/选项：/答案：」键值格式，
            也支持常见的试卷格式；格式混乱还可以用 AI 智能整理（设置里配置）。
          </Typography.Paragraph>
        )}
        {step === 1 && (
          <Typography.Paragraph>
            每次作答即时判分；填空题忽略大小写和全半角，同一空的多个正确写法用「|」分隔。
            答错的题自动进错题本，不需要手动标记。
          </Typography.Paragraph>
        )}
        {step === 2 && (
          <Typography.Paragraph>
            没有现成的题库文件？先导入内置示例题库体验完整流程（覆盖四种题型，可随时删除）。
          </Typography.Paragraph>
        )}
      </Space>
    </Modal>
  );
}
