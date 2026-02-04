import { useQuery } from '@tanstack/react-query';
import { dashboardApi } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Users, MessageSquare, Coins, Shield } from 'lucide-react';

function StatCard({ title, value, icon: Icon, subtitle }: { title: string; value: string | number; icon: typeof Users; subtitle?: string }) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
        <Icon className="h-4 w-4 text-muted-foreground" />
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">{value}</div>
        {subtitle && <p className="text-xs text-muted-foreground">{subtitle}</p>}
      </CardContent>
    </Card>
  );
}

export function DashboardPage() {
  const { data: stats, isLoading } = useQuery({
    queryKey: ['dashboard', 'stats'],
    queryFn: dashboardApi.getStats,
  });

  const { data: activity } = useQuery({
    queryKey: ['dashboard', 'activity'],
    queryFn: () => dashboardApi.getActivity(7),
  });

  if (isLoading) {
    return <div>Loading...</div>;
  }

  return (
    <div className="space-y-6">
      <h2 className="text-3xl font-bold">Dashboard</h2>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Total Students"
          value={stats?.students || 0}
          icon={Users}
        />
        <StatCard
          title="Conversations Today"
          value={stats?.conversations_today || 0}
          icon={MessageSquare}
          subtitle={`Total: ${stats?.conversations || 0}`}
        />
        <StatCard
          title="Tokens Today"
          value={(stats?.tokens_today || 0).toLocaleString()}
          icon={Coins}
          subtitle={`Total: ${(stats?.total_tokens || 0).toLocaleString()}`}
        />
        <StatCard
          title="Blocked Requests"
          value={stats?.blocked || 0}
          icon={Shield}
        />
      </div>

      {activity && activity.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Recent Activity (7 days)</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-sm text-muted-foreground">
              Activity data available: {activity.length} days
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
