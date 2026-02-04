import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { conversationsApi } from '@/lib/api';
import { Card, CardContent } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import type { Conversation } from '@/types';

export function ConversationsPage() {
  const [filters, setFilters] = useState({ action: '', student_id: '' });

  const { data, isLoading } = useQuery({
    queryKey: ['conversations', filters],
    queryFn: () => conversationsApi.list({ limit: 100, ...filters }),
  });

  const getActionBadge = (action: string) => {
    switch (action) {
      case 'blocked': return <Badge variant="destructive">Blocked</Badge>;
      case 'guided': return <Badge variant="secondary">Guided</Badge>;
      default: return <Badge variant="outline">Passed</Badge>;
    }
  };

  if (isLoading) return <div>Loading...</div>;

  return (
    <div className="space-y-6">
      <h2 className="text-3xl font-bold">Conversations</h2>

      <div className="flex gap-4">
        <Select onValueChange={v => setFilters({...filters, action: v})}>
          <SelectTrigger className="w-40">
            <SelectValue placeholder="Filter by action" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="">All</SelectItem>
            <SelectItem value="blocked">Blocked</SelectItem>
            <SelectItem value="guided">Guided</SelectItem>
            <SelectItem value="passed">Passed</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Time</TableHead>
                <TableHead>Student</TableHead>
                <TableHead>Action</TableHead>
                <TableHead>Tokens</TableHead>
                <TableHead>Details</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data?.items.map((conv: Conversation) => (
                <TableRow key={conv.id}>
                  <TableCell>{new Date(conv.timestamp).toLocaleString()}</TableCell>
                  <TableCell className="font-mono text-xs">{conv.student_id.slice(0, 8)}...</TableCell>
                  <TableCell>{getActionBadge(conv.action_taken)}</TableCell>
                  <TableCell>{conv.tokens_used}</TableCell>
                  <TableCell>
                    <Dialog>
                      <DialogTrigger asChild>
                        <Button variant="ghost" size="sm">View</Button>
                      </DialogTrigger>
                      <DialogContent className="max-w-2xl">
                        <DialogHeader>
                          <DialogTitle>Conversation Details</DialogTitle>
                        </DialogHeader>
                        <div className="space-y-4">
                          <div>
                            <h4 className="font-semibold mb-1">Prompt:</h4>
                            <p className="text-sm bg-slate-100 p-2 rounded">{conv.prompt_text}</p>
                          </div>
                          <div>
                            <h4 className="font-semibold mb-1">Response:</h4>
                            <p className="text-sm bg-slate-100 p-2 rounded">{conv.response_text}</p>
                          </div>
                          {conv.rule_triggered && (
                            <div>
                              <h4 className="font-semibold mb-1">Rule Triggered:</h4>
                              <Badge>{conv.rule_triggered}</Badge>
                            </div>
                          )}
                        </div>
                      </DialogContent>
                    </Dialog>
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
