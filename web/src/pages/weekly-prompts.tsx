import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { promptsApi } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Switch } from '@/components/ui/switch';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Label } from '@/components/ui/label';
import { Trash2 } from 'lucide-react';
import type { WeeklyPrompt } from '@/types';

export function WeeklyPromptsPage() {
  const queryClient = useQueryClient();
  const [newPrompt, setNewPrompt] = useState({
    week_start: 1,
    week_end: 4,
    system_prompt: '',
    description: '',
    is_active: true
  });

  const { data: prompts, isLoading } = useQuery({
    queryKey: ['prompts'],
    queryFn: promptsApi.list,
  });

  const { data: currentPrompt } = useQuery({
    queryKey: ['prompts', 'current'],
    queryFn: promptsApi.getCurrent,
  });

  const createMutation = useMutation({
    mutationFn: promptsApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['prompts'] });
      setNewPrompt({ week_start: 1, week_end: 4, system_prompt: '', description: '', is_active: true });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: promptsApi.delete,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['prompts'] }),
  });

  if (isLoading) return <div>Loading...</div>;

  return (
    <div className="space-y-6">
      <h2 className="text-3xl font-bold">Weekly Prompts</h2>

      {currentPrompt && (
        <Card className="bg-blue-50 border-blue-200">
          <CardHeader>
            <CardTitle className="text-blue-800">Current Week Prompt</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-blue-600 mb-2">Weeks {currentPrompt.week_start}-{currentPrompt.week_end}</p>
            <p className="text-sm">{currentPrompt.system_prompt.slice(0, 200)}...</p>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Create New Prompt</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label>Week Start</Label>
              <Input
                type="number" min={1} max={20}
                value={newPrompt.week_start}
                onChange={e => setNewPrompt({...newPrompt, week_start: parseInt(e.target.value)})}
              />
            </div>
            <div>
              <Label>Week End</Label>
              <Input
                type="number" min={1} max={20}
                value={newPrompt.week_end}
                onChange={e => setNewPrompt({...newPrompt, week_end: parseInt(e.target.value)})}
              />
            </div>
          </div>
          <div>
            <Label>Description</Label>
            <Input
              value={newPrompt.description}
              onChange={e => setNewPrompt({...newPrompt, description: e.target.value})}
              placeholder="e.g., Week 1-2: Introduction"
            />
          </div>
          <div>
            <Label>System Prompt</Label>
            <Textarea
              value={newPrompt.system_prompt}
              onChange={e => setNewPrompt({...newPrompt, system_prompt: e.target.value})}
              placeholder="Enter system prompt..."
              rows={5}
            />
          </div>
          <div className="flex items-center gap-2">
            <Switch
              checked={newPrompt.is_active}
              onCheckedChange={v => setNewPrompt({...newPrompt, is_active: v})}
            />
            <Label>Active</Label>
          </div>
          <Button onClick={() => createMutation.mutate(newPrompt)}>Create Prompt</Button>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Weeks</TableHead>
                <TableHead>Description</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {prompts?.map((prompt: WeeklyPrompt) => (
                <TableRow key={prompt.id}>
                  <TableCell>Week {prompt.week_start}-{prompt.week_end}</TableCell>
                  <TableCell>{prompt.description || '-'}</TableCell>
                  <TableCell>
                    {prompt.is_active ? (
                      <Badge className="bg-green-500">Active</Badge>
                    ) : (
                      <Badge variant="secondary">Inactive</Badge>
                    )}
                  </TableCell>
                  <TableCell>
                    <Button variant="ghost" size="icon" onClick={() => deleteMutation.mutate(prompt.id)}>
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
