// 仪表盘首页：练习总览 + 正确率趋势 + 最近练习 + 各题库进度（spec P3）
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import {
  Button,
  Card,
  Col,
  Empty,
  List,
  Progress,
  Row,
  Space,
  Statistic,
  Tag,
  Typography,
  theme,
} from 'antd';
import {
  BookOutlined,
  DatabaseOutlined,
  RightOutlined,
  TrophyOutlined,
} from '@ant-design/icons';
import { getStatsOverview } from '../api';
import type { StatsOverview } from '../api';
import { useBanks } from '../api/queries';

type Overview = StatsOverview;
type TrendPoint = StatsOverview['trend'][number];

/** 近 14 天每日正确率竖条（纯 CSS，不引图表库） */
function TrendBars({ trend }: { trend: TrendPoint[] }) {
  const { token } = theme.useToken();
  const maxAttempts = Math.max(1, ...trend.map((t) => t.attempts));
  return (
    <div style={{ display: 'flex', alignItems: 'flex-end', gap: 4, height: 120 }}>
      {trend.map((t) => {
        const rate = t.attempts ? t.correct / t.attempts : 0;
        return (
          <div
            key={t.date}
            title={`${t.date}：作答 ${t.attempts} 次，正确 ${t.correct} 次`}
            style={{
              flex: 1,
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'flex-end',
              height: '100%',
            }}
          >
            <div
              style={{
                height: t.attempts
                  ? `${Math.max(6, (t.attempts / maxAttempts) * 100)}%`
                  : 2,
                background: t.attempts
                  ? `linear-gradient(to top, ${token.colorSuccess} ${rate * 100}%, ${token.colorBorderSecondary} ${rate * 100}%)`
                  : token.colorBorderSecondary,
                borderRadius: 3,
                minHeight: 2,
              }}
            />
            <Typography.Text
              type="secondary"
              style={{ fontSize: 10, textAlign: 'center', marginTop: 4 }}
            >
              {t.date.slice(5)}
            </Typography.Text>
          </div>
        );
      })}
    </div>
  );
}

export default function DashboardPage() {
  const navigate = useNavigate();
  const { data: banks = [] } = useBanks();
  const { data, isLoading } = useQuery({
    queryKey: ['stats', 'overview'],
    queryFn: getStatsOverview,
  });

  if (!isLoading && data && data.total_attempts === 0 && banks.length === 0) {
    return (
      <Empty description="还没有题库，先导入一份开始刷题吧" style={{ marginTop: 80 }}>
        <Space>
          <Button type="primary" onClick={() => navigate('/quiz/start')}>
            先去刷题
          </Button>
          <Button onClick={() => navigate('/banks')}>管理题库</Button>
        </Space>
      </Empty>
    );
  }

  const overview: Overview | undefined = data;

  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      <Typography.Title level={4} style={{ margin: 0 }}>
        总览
      </Typography.Title>

      <Row gutter={[16, 16]}>
        <Col xs={12} md={5}>
          <Card size="small">
            <Statistic
              title="题库"
              value={overview?.total_banks ?? 0}
              prefix={<DatabaseOutlined />}
            />
          </Card>
        </Col>
        <Col xs={12} md={5}>
          <Card size="small">
            <Statistic title="题目" value={overview?.total_questions ?? 0} />
          </Card>
        </Col>
        <Col xs={12} md={5}>
          <Card size="small">
            <Statistic title="累计作答" value={overview?.total_attempts ?? 0} />
          </Card>
        </Col>
        <Col xs={12} md={5}>
          <Card size="small">
            <Statistic
              title="总正确率"
              value={overview?.accuracy ?? 0}
              precision={1}
              suffix="%"
              prefix={<TrophyOutlined />}
            />
          </Card>
        </Col>
        <Col xs={12} md={4}>
          <Card
            size="small"
            hoverable
            onClick={() => navigate('/mistakes')}
          >
            <Statistic
              title="待复习错题"
              value={overview?.pending_mistakes ?? 0}
              prefix={<BookOutlined />}
            />
          </Card>
        </Col>
      </Row>

      <Card size="small" title="正确率趋势（近 14 天，绿色为正确占比）">
        <TrendBars trend={overview?.trend ?? []} />
      </Card>

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={12}>
          <Card
            size="small"
            title="最近练习"
            extra={
              <Button type="link" size="small" onClick={() => navigate('/quiz/start')}>
                开始练习 <RightOutlined />
              </Button>
            }
          >
            <List
              size="small"
              loading={isLoading}
              locale={{ emptyText: '还没有练习记录' }}
              dataSource={overview?.recent_sessions ?? []}
              renderItem={(s) => (
                <List.Item
                  extra={
                    <Tag color={s.accuracy >= 60 ? 'success' : 'error'}>
                      {s.accuracy}%
                    </Tag>
                  }
                >
                  <List.Item.Meta
                    title={`${s.bank_name} · ${s.mode}练习`}
                    description={`${new Date(s.created_at).toLocaleString()} · 作答 ${s.answered}/${s.total} 题，答对 ${s.correct}`}
                  />
                </List.Item>
              )}
            />
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card
            size="small"
            title="题库进度"
            extra={
              <Button type="link" size="small" onClick={() => navigate('/banks')}>
                管理题库 <RightOutlined />
              </Button>
            }
          >
            <List
              size="small"
              loading={isLoading}
              locale={{ emptyText: '暂无题库' }}
              dataSource={overview?.bank_progress ?? []}
              renderItem={(b) => (
                <List.Item>
                  <List.Item.Meta
                    title={`${b.bank_name}（${b.question_count} 题）`}
                    description={
                      <Progress
                        percent={b.progress}
                        size="small"
                        format={() =>
                          `${b.answered_questions}/${b.question_count} 已作答 · 正确率 ${b.accuracy}%`
                        }
                      />
                    }
                  />
                </List.Item>
              )}
            />
          </Card>
        </Col>
      </Row>
    </Space>
  );
}
