// 题目新增/编辑表单弹窗：按题型动态显示选项与答案字段
import { useEffect } from 'react';
import {
  Form,
  Input,
  InputNumber,
  Modal,
  Radio,
  Select,
  Space,
} from 'antd';
import type { CreateQuestionDTO, Question, QuestionType } from '../api/types';
import { QUESTION_TYPE_LABELS } from '../api/types';

const { TextArea } = Input;
const OPTION_KEYS = ['A', 'B', 'C', 'D', 'E', 'F'];

interface FormValues {
  type: QuestionType;
  content: string;
  score: number;
  options?: Record<string, string>;
  /** 单选模式下 Select 返回字符串，多选返回数组 */
  answer?: string[] | string;
  blankAnswer?: string;
  judgeAnswer?: string;
}

interface QuestionFormModalProps {
  open: boolean;
  bankId: number;
  /** 传入则为编辑模式 */
  question?: Question | null;
  onCancel: () => void;
  onSubmit: (dto: CreateQuestionDTO) => Promise<void>;
}

export default function QuestionFormModal({
  open,
  bankId,
  question,
  onCancel,
  onSubmit,
}: QuestionFormModalProps) {
  const [form] = Form.useForm<FormValues>();
  const type = Form.useWatch('type', form);
  const isChoice = type === 'single' || type === 'multi';

  useEffect(() => {
    if (!open) return;
    if (question) {
      const options: Record<string, string> = {};
      for (const key of OPTION_KEYS) {
        options[key] = question.options?.[key] ?? '';
      }
      form.setFieldsValue({
        type: question.type,
        content: question.content,
        score: question.score,
        options,
        // 单选模式 Select 只接受字符串值
        answer:
          question.type === 'single'
            ? question.answer?.[0]
            : question.answer ?? [],
        blankAnswer: question.blank_answer?.[0] ?? question.answer?.[0] ?? '',
        judgeAnswer: question.answer?.[0],
      });
    } else {
      form.resetFields();
    }
  }, [open, question, form]);

  const handleOk = async () => {
    const values = await form.validateFields();

    const dto: CreateQuestionDTO = {
      bank_id: bankId,
      type: values.type,
      content: values.content.trim(),
      score: values.score,
    };

    if (isChoice) {
      const options: Record<string, string> = {};
      for (const key of OPTION_KEYS) {
        const text = values.options?.[key]?.trim();
        if (text) options[key] = text;
      }
      dto.options = options;
      // 单选返回字符串，多选返回数组，统一归一化为数组
      dto.answer = Array.isArray(values.answer)
        ? values.answer
        : values.answer
          ? [values.answer]
          : [];
    } else if (values.type === 'judge') {
      dto.answer = [values.judgeAnswer!];
    } else if (values.type === 'blank') {
      dto.blank_answer = [values.blankAnswer!.trim()];
    }

    await onSubmit(dto);
  };

  return (
    <Modal
      title={question ? '编辑题目' : '新增题目'}
      open={open}
      onCancel={onCancel}
      onOk={handleOk}
      okText="保存"
      cancelText="取消"
      width={640}
      destroyOnClose
    >
      <Form
        form={form}
        layout="vertical"
        initialValues={{ type: 'single', score: 1.0 }}
      >
        <Space size="large">
          <Form.Item
            name="type"
            label="题型"
            rules={[{ required: true, message: '请选择题型' }]}
          >
            <Select
              style={{ width: 140 }}
              options={Object.entries(QUESTION_TYPE_LABELS).map(
                ([value, label]) => ({ value, label }),
              )}
            />
          </Form.Item>
          <Form.Item
            name="score"
            label="分数"
            rules={[{ required: true, message: '请输入分数' }]}
          >
            <InputNumber min={0.5} step={0.5} />
          </Form.Item>
        </Space>

        <Form.Item
          name="content"
          label="题目内容"
          rules={[{ required: true, message: '请输入题目内容' }]}
        >
          <TextArea rows={3} placeholder="请输入题干" />
        </Form.Item>

        {isChoice && (
          <>
            <Form.Item label="选项（留空的选项将被忽略）" required>
              <Space direction="vertical" style={{ width: '100%' }}>
                {OPTION_KEYS.map((key) => (
                  <Space key={key} style={{ width: '100%' }}>
                    <span style={{ width: 20, display: 'inline-block' }}>
                      {key}.
                    </span>
                    <Form.Item name={['options', key]} noStyle>
                      <Input
                        style={{ width: 480 }}
                        placeholder={`选项 ${key} 内容`}
                      />
                    </Form.Item>
                  </Space>
                ))}
              </Space>
            </Form.Item>
            <Form.Item
              name="answer"
              label="正确答案"
              rules={[{ required: true, message: '请选择正确答案' }]}
            >
              <Select
                mode={type === 'multi' ? 'multiple' : undefined}
                placeholder="选择正确选项"
                options={OPTION_KEYS.map((key) => ({ value: key, label: key }))}
                style={{ width: 240 }}
              />
            </Form.Item>
          </>
        )}

        {type === 'judge' && (
          <Form.Item
            name="judgeAnswer"
            label="正确答案"
            rules={[{ required: true, message: '请选择正确答案' }]}
          >
            <Radio.Group>
              <Radio value="对">对</Radio>
              <Radio value="错">错</Radio>
            </Radio.Group>
          </Form.Item>
        )}

        {type === 'blank' && (
          <Form.Item
            name="blankAnswer"
            label="正确答案"
            rules={[{ required: true, message: '请输入正确答案' }]}
          >
            <Input placeholder="填空题答案" />
          </Form.Item>
        )}
      </Form>
    </Modal>
  );
}
