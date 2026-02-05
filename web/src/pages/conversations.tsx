import { useState, useCallback } from 'react';
import { useQuery } from '@tanstack/react-query';
import { conversationsApi, studentsApi } from '@/lib/api';
import { Card, CardContent } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Search, User, MessageSquare, Download, X } from 'lucide-react';
import { useDebounce } from '@/hooks/use-debounce';
import type { Conversation, Student } from '@/types';

export function ConversationsPage() {
  const [filters, setFilters] = useState({ 
    action: 'all', 
    student_id: 'all',
    search: '' 
  });
  
  // Debounce search query
  const debouncedSearch = useDebounce(filters.search, 300);

  const { data: students } = useQuery({
    queryKey: ['students'],
    queryFn: studentsApi.list,
  });

  const { data, isLoading, error } = useQuery({
    queryKey: ['conversations', filters.action, filters.student_id, debouncedSearch],
    queryFn: () => {
      const params: Record<string, string | number> = { limit: 100 };
      if (filters.action !== 'all') params.action = filters.action;
      if (filters.student_id !== 'all') params.student_id = filters.student_id;
      if (debouncedSearch) params.search = debouncedSearch;
      return conversationsApi.list(params);
    },
  });

  const getActionBadge = (action: string) => {
    switch (action) {
      case 'blocked': return <Badge variant="destructive">Blocked</Badge>;
      case 'guided': return <Badge variant="secondary">Guided</Badge>;
      default: return <Badge variant="outline">Passed</Badge>;
    }
  };

  const exportToJSON = useCallback(() => {
    if (!data?.items) return;
    const blob = new Blob([JSON.stringify(data.items, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `conversations-${new Date().toISOString().split('T')[0]}.json`;
    a.click();
  }, [data]);

  const clearFilters = () => {
    setFilters({ action: 'all', student_id: 'all', search: '' });
  };

  if (isLoading) return <div className="p-8">Loading conversations...</div>;

  if (error) {
    return (
      <div className="space-y-6 p-8">
        <h2 className="text-3xl font-bold">Conversations</h2>
        <Card className="bg-red-50 border-red-200">
          <CardContent className="pt-6">
            <p className="text-red-600">Error loading conversations: {(error as Error)?.message || 'Unknown error'}</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  const conversations = data?.items || [];
  const hasFilters = filters.action !== 'all' || filters.student_id !== 'all' || filters.search;

  return (
    <div className="space-y-6 p-8">
      <div className="flex justify-between items-center">
        <h2 className="text-3xl font-bold">Conversations</h2>
        <Button variant="outline" onClick={exportToJSON} disabled={conversations.length === 0}>
          <Download className="mr-2 h-4 w-4" /> Export JSON
        </Button>
      </div>

      {/* Search and Filters */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex flex-wrap gap-4 items-end">
            {/* Search */}
            <div className="flex-1 min-w-[200px]">
              <label className="text-sm font-medium mb-2 block">Search Content</label>
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
                <Input
                  placeholder="Search in prompts or responses..."
                  value={filters.search}
                  onChange={(e) => setFilters({ ...filters, search: e.target.value })}
                  className="pl-10"
                />
                {filters.search && (
                  <button
                    onClick={() => setFilters({ ...filters, search: '' })}
                    className="absolute right-3 top-1/2 transform -translate-y-1/2"
                  >
                    <X className="h-4 w-4 text-gray-400 hover:text-gray-600" />
                  </button>
                )}
              </div>
            </div>

            {/* Student Filter */}
            <div className="w-48">
              <label className="text-sm font-medium mb-2 block flex items-center gap-2">
                <User className="h-4 w-4" /> Student
              </label>
              <Select 
                value={filters.student_id} 
                onValueChange={(v) => setFilters({ ...filters, student_id: v })}
              >
                <SelectTrigger>
                  <SelectValue placeholder="All students" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Students</SelectItem>
                  {students?.map((s: Student) => (
                    <SelectItem key={s.id} value={s.id}>{s.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Action Filter */}
            <div className="w-40">
              <label className="text-sm font-medium mb-2 block flex items-center gap-2">
                <MessageSquare className="h-4 w-4" /> Action
              </label>
              <Select 
                value={filters.action} 
                onValueChange={(v) => setFilters({ ...filters, action: v })}
              >
                <SelectTrigger>
                  <SelectValue placeholder="All actions" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Actions</SelectItem>
                  <SelectItem value="blocked">Blocked</SelectItem>
                  <SelectItem value="guided">Guided</SelectItem>
                  <SelectItem value="passed">Passed</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Clear Filters */}
            {hasFilters && (
              <Button variant="ghost" onClick={clearFilters} className="h-10">
                <X className="mr-2 h-4 w-4" /> Clear
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Results Summary */}
      <div className="flex justify-between items-center text-sm text-gray-500">
        <span>Showing {conversations.length} of {data?.total || 0} conversations</span>
        {debouncedSearch && <span>Search: "{debouncedSearch}"</span>}
      </div>

      {/* Conversations Table */}
      <Card>
        <CardContent className="p-0">
          {conversations.length === 0 ? (
            <div className="p-8 text-center text-gray-500">
              {hasFilters ? 'No conversations match your filters' : 'No conversations found'}
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Time</TableHead>
                  <TableHead>Student</TableHead>
                  <TableHead>Action</TableHead>
                  <TableHead>Tokens</TableHead>
                  <TableHead>Preview</TableHead>
                  <TableHead>Details</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {conversations.map((conv: Conversation) => (
                  <TableRow key={conv.id}>
                    <TableCell className="whitespace-nowrap">
                      {conv.timestamp ? new Date(conv.timestamp).toLocaleString() : 'N/A'}
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <User className="h-4 w-4 text-gray-400" />
                        <span className="font-mono text-xs">{conv.student_id?.slice(0, 8)}...</span>
                      </div>
                    </TableCell>
                    <TableCell>{getActionBadge(conv.action_taken || 'passed')}</TableCell>
                    <TableCell>{conv.tokens_used || 0}</TableCell>
                    <TableCell className="max-w-xs">
                      <p className="text-sm text-gray-600 truncate">
                        {conv.prompt_text?.substring(0, 50)}...
                      </p>
                    </TableCell>
                    <TableCell>
                      <Dialog>
                        <DialogTrigger asChild>
                          <Button variant="ghost" size="sm">View</Button>
                        </DialogTrigger>
                        <DialogContent className="max-w-3xl max-h-[85vh] overflow-y-auto">
                          <DialogHeader>
                            <DialogTitle>Conversation Details</DialogTitle>
                          </DialogHeader>
                          
                          <div className="space-y-4">
                            {/* Metadata */}
                            <div className="flex flex-wrap gap-4 text-sm text-gray-500 bg-gray-50 p-3 rounded">
                              <span><strong>ID:</strong> {conv.id}</span>
                              <span><strong>Student:</strong> {conv.student_id}</span>
                              <span><strong>Time:</strong> {conv.timestamp ? new Date(conv.timestamp).toLocaleString() : 'N/A'}</span>
                              <span><strong>Week:</strong> {conv.week_number}</span>
                              <span><strong>Tokens:</strong> {conv.tokens_used}</span>
                              {conv.model && <span><strong>Model:</strong> {conv.model}</span>}
                            </div>

                            {/* Prompt */}
                            <div>
                              <h4 className="font-semibold mb-2 text-blue-600 flex items-center gap-2">
                                <MessageSquare className="h-4 w-4" /> Prompt:
                              </h4>
                              <div className="bg-blue-50 p-4 rounded-lg">
                                <p className="text-sm whitespace-pre-wrap">{conv.prompt_text || 'N/A'}</p>
                              </div>
                            </div>

                            {/* Response */}
                            <div>
                              <h4 className="font-semibold mb-2 text-green-600 flex items-center gap-2">
                                <MessageSquare className="h-4 w-4" /> Response:
                              </h4>
                              <div className="bg-green-50 p-4 rounded-lg">
                                <p className="text-sm whitespace-pre-wrap">{conv.response_text || 'N/A'}</p>
                              </div>
                            </div>

                            {/* Rule Info */}
                            {conv.rule_triggered && (
                              <div className="bg-yellow-50 border border-yellow-200 p-4 rounded-lg">
                                <h4 className="font-semibold mb-2 text-yellow-700">Rule Triggered:</h4>
                                <Badge variant="secondary">{conv.rule_triggered}</Badge>
                                <p className="mt-2 text-sm text-yellow-600">
                                  Action: {conv.action_taken}
                                </p>
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
          )}
        </CardContent>
      </Card>
    </div>
  );
}
