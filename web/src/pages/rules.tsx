import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { rulesApi } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Switch } from '@/components/ui/switch';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Label } from '@/components/ui/label';
import { RefreshCw, Trash2 } from 'lucide-react';
import type { Rule } from '@/types';

export function RulesPage() {
  const queryClient = useQueryClient();
  const [newRule, setNewRule] = useState<{ pattern: string; rule_type: 'block' | 'guide'; message: string; active_weeks: string }>({ pattern: '', rule_type: 'block', message: '', active_weeks: '1-16' });

  const { data: rules, isLoading } = useQuery({
    queryKey: ['rules'],
    queryFn: rulesApi.list,
  });

  const createMutation = useMutation({
    mutationFn: rulesApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['rules'] });
      setNewRule({ pattern: '', rule_type: 'block', message: '', active_weeks: '1-16' });
    },
  });

  const toggleMutation = useMutation({
    mutationFn: rulesApi.toggle,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['rules'] }),
  });

  const deleteMutation = useMutation({
    mutationFn: rulesApi.delete,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['rules'] }),
  });

  const reloadMutation = useMutation({
    mutationFn: rulesApi.reloadCache,
  });

  if (isLoading) return <div>Loading...</div>;

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-3xl font-bold">Rules</h2>
        <Button variant="outline" onClick={() => reloadMutation.mutate()}>
          <RefreshCw className="mr-2 h-4 w-4" /> Reload Cache
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Create New Rule</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label>Pattern (Regex)</Label>
              <Input
                value={newRule.pattern}
                onChange={e => setNewRule({...newRule, pattern: e.target.value})}
                placeholder="e.g., .*write.*code.*"
              />
            </div>
            <div>
              <Label>Type</Label>
              <Select value={newRule.rule_type} onValueChange={v => setNewRule({...newRule, rule_type: v as 'block' | 'guide'})}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="block">Block</SelectItem>
                  <SelectItem value="guide">Guide</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <div>
            <Label>Message</Label>
            <Textarea
              value={newRule.message}
              onChange={e => setNewRule({...newRule, message: e.target.value})}
              placeholder="Message to return when rule matches..."
            />
          </div>
          <div>
            <Label>Active Weeks</Label>
            <Input
              value={newRule.active_weeks}
              onChange={e => setNewRule({...newRule, active_weeks: e.target.value})}
              placeholder="e.g., 1-4, 8-12"
            />
          </div>
          <Button onClick={() => createMutation.mutate({ ...newRule, enabled: true })}>Create Rule</Button>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Pattern</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Active Weeks</TableHead>
                <TableHead>Enabled</TableHead>
                <TableHead>Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rules?.map((rule: Rule) => (
                <TableRow key={rule.id}>
                  <TableCell className="font-mono text-xs max-w-xs truncate">{rule.pattern}</TableCell>
                  <TableCell>
                    <Badge variant={rule.rule_type === 'block' ? 'destructive' : 'secondary'}>
                      {rule.rule_type}
                    </Badge>
                  </TableCell>
                  <TableCell>{rule.active_weeks}</TableCell>
                  <TableCell>
                    <Switch
                      checked={rule.enabled}
                      onCheckedChange={() => toggleMutation.mutate(rule.id)}
                    />
                  </TableCell>
                  <TableCell>
                    <Button variant="ghost" size="icon" onClick={() => deleteMutation.mutate(rule.id)}>
                      <Trash2 className="h-4 w-4 text-red-500" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
