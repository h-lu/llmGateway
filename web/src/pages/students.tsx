import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { studentsApi, conversationsApi } from '@/lib/api';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Plus, Key, RotateCcw, Trash2, MessageSquare, User, Search } from 'lucide-react';
import type { Student, Conversation } from '@/types';

export function StudentsPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');
  const [newStudent, setNewStudent] = useState({ name: '', email: '', quota: 10000 });
  const [createdKey, setCreatedKey] = useState<string | null>(null);
  const [createError, setCreateError] = useState<string | null>(null);
  const [selectedStudent, setSelectedStudent] = useState<Student | null>(null);

  const { data: students, isLoading } = useQuery({
    queryKey: ['students'],
    queryFn: studentsApi.list,
  });

  const { data: studentConversations, isLoading: conversationsLoading } = useQuery({
    queryKey: ['student-conversations', selectedStudent?.id],
    queryFn: () => selectedStudent ? conversationsApi.getByStudent(selectedStudent.id) : Promise.resolve({ items: [], total: 0 }),
    enabled: !!selectedStudent,
  });

  const createMutation = useMutation({
    mutationFn: studentsApi.create,
    onSuccess: (data) => {
      setCreatedKey(data.api_key);
      setCreateError(null);
      queryClient.invalidateQueries({ queryKey: ['students'] });
    },
    onError: (error: unknown) => {
      const maybeErr = error as { response?: { data?: { detail?: unknown } }; message?: unknown };
      const detail = maybeErr.response?.data?.detail;
      const message =
        (typeof detail === 'string' && detail) ||
        (typeof maybeErr.message === 'string' && maybeErr.message) ||
        'Failed to create student';
      setCreateError(message);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: studentsApi.delete,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['students'] }),
  });

  const regenerateMutation = useMutation({
    mutationFn: studentsApi.regenerateKey,
    onSuccess: (data) => {
      setCreatedKey(data.api_key);
    },
  });

  const filteredStudents = students?.filter((s: Student) =>
    s.name.toLowerCase().includes(search.toLowerCase()) ||
    s.email.toLowerCase().includes(search.toLowerCase())
  );

  const getUsageBadge = (used: number, quota: number) => {
    const pct = quota > 0 ? (used / quota) * 100 : 0;
    if (pct >= 100) return <Badge variant="destructive">Exhausted</Badge>;
    if (pct >= 80) return <Badge variant="secondary">Warning</Badge>;
    if (used === 0) return <Badge variant="outline">Unused</Badge>;
    return <Badge className="bg-green-500">Normal</Badge>;
  };

  const getActionBadge = (action: string) => {
    switch (action) {
      case 'blocked': return <Badge variant="destructive">Blocked</Badge>;
      case 'guided': return <Badge variant="secondary">Guided</Badge>;
      default: return <Badge variant="outline">Passed</Badge>;
    }
  };

  if (isLoading) return <div className="p-8">Loading...</div>;

  return (
    <div className="space-y-6 p-8">
      <div className="flex justify-between items-center">
        <h2 className="text-3xl font-bold">Students</h2>
        <Dialog onOpenChange={(open) => open && setCreateError(null)}>
          <DialogTrigger asChild>
            <Button><Plus className="mr-2 h-4 w-4" /> Add Student</Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Create New Student</DialogTitle>
              <DialogDescription>Create a student account and generate an API key.</DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div>
                <Label htmlFor="new-student-name">Name</Label>
                <Input
                  id="new-student-name"
                  value={newStudent.name}
                  onChange={e => setNewStudent({...newStudent, name: e.target.value})}
                />
              </div>
              <div>
                <Label htmlFor="new-student-email">Email</Label>
                <Input
                  id="new-student-email"
                  type="email"
                  value={newStudent.email}
                  onChange={e => setNewStudent({...newStudent, email: e.target.value})}
                />
              </div>
              <div>
                <Label htmlFor="new-student-quota">Weekly Quota</Label>
                <Input
                  id="new-student-quota"
                  type="number"
                  value={newStudent.quota}
                  onChange={e => {
                    const quota = Number.parseInt(e.target.value, 10);
                    setNewStudent({...newStudent, quota: Number.isFinite(quota) ? quota : 0});
                  }}
                />
              </div>
              <Button
                onClick={() => createMutation.mutate(newStudent)}
                disabled={!newStudent.name || !newStudent.email || createMutation.isPending}
              >
                {createMutation.isPending ? 'Creating...' : 'Create'}
              </Button>
              {createError && (
                <p role="alert" className="text-sm text-red-600">
                  {createError}
                </p>
              )}
            </div>
          </DialogContent>
        </Dialog>
      </div>

      {createdKey && (
        <Card className="bg-yellow-50 border-yellow-200">
          <CardContent className="pt-6">
            <p className="font-semibold text-yellow-800 mb-2">API Key Generated (save this!)</p>
            <code className="bg-yellow-100 px-2 py-1 rounded">{createdKey}</code>
            <Button variant="ghost" size="sm" onClick={() => setCreatedKey(null)} className="ml-2">Dismiss</Button>
          </CardContent>
        </Card>
      )}

      <div className="relative">
        <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
        <Input
          placeholder="Search students by name or email..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="pl-10 max-w-md"
        />
      </div>

      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Email</TableHead>
                <TableHead>Quota</TableHead>
                <TableHead>Used</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredStudents?.map((student: Student) => (
                <TableRow key={student.id}>
                  <TableCell className="font-medium">{student.name}</TableCell>
                  <TableCell>{student.email}</TableCell>
                  <TableCell>{student.current_week_quota.toLocaleString()}</TableCell>
                  <TableCell>{student.used_quota.toLocaleString()}</TableCell>
                  <TableCell>{getUsageBadge(student.used_quota, student.current_week_quota)}</TableCell>
                  <TableCell>
                    <div className="flex gap-2">
                      {/* View Conversations */}
                      <Dialog>
                        <DialogTrigger asChild>
                          <Button 
                            variant="ghost" 
                            size="sm"
                            onClick={() => setSelectedStudent(student)}
                            title="View Conversations"
                            className="flex items-center gap-1"
                          >
                            <MessageSquare className="h-4 w-4 text-blue-500" />
                            <span className="text-xs">View</span>
                          </Button>
                        </DialogTrigger>
                        <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
                          <DialogHeader>
                            <DialogTitle className="flex items-center gap-2">
                              <User className="h-5 w-5" />
                              {student.name}'s Conversations
                            </DialogTitle>
                          </DialogHeader>
                          
                          <Tabs defaultValue="conversations" className="mt-4">
                            <TabsList>
                              <TabsTrigger value="conversations">
                                <MessageSquare className="mr-2 h-4 w-4" /> Conversations
                              </TabsTrigger>
                              <TabsTrigger value="info">
                                <User className="mr-2 h-4 w-4" /> Student Info
                              </TabsTrigger>
                            </TabsList>
                            
                            <TabsContent value="conversations" className="mt-4">
                              {conversationsLoading ? (
                                <div className="p-8 text-center">Loading conversations...</div>
                              ) : studentConversations?.items.length === 0 ? (
                                <div className="p-8 text-center">
                                  <MessageSquare className="h-12 w-12 text-gray-300 mx-auto mb-4" />
                                  <p className="text-gray-500">No conversations found for {student.name}</p>
                                  <p className="text-sm text-gray-400 mt-2">This student hasn't started any conversations yet.</p>
                                </div>
                              ) : (
                                <div className="space-y-4">
                                  <p className="text-sm text-gray-500">
                                    Total: {studentConversations?.total} conversations
                                  </p>
                                  <div className="space-y-4 max-h-[60vh] overflow-y-auto">
                                    {studentConversations?.items.map((conv: Conversation) => (
                                      <Card key={conv.id} className="border-l-4 border-l-blue-500">
                                        <CardContent className="p-4">
                                          <div className="flex justify-between items-start mb-2">
                                            <span className="text-sm text-gray-500">
                                              {conv.timestamp ? new Date(conv.timestamp).toLocaleString() : 'N/A'}
                                            </span>
                                            {getActionBadge(conv.action_taken || 'passed')}
                                          </div>
                                          <div className="space-y-2">
                                            <div>
                                              <p className="text-xs font-semibold text-blue-600">Prompt:</p>
                                              <p className="text-sm bg-blue-50 p-2 rounded">{conv.prompt_text}</p>
                                            </div>
                                            <div>
                                              <p className="text-xs font-semibold text-green-600">Response:</p>
                                              <p className="text-sm bg-green-50 p-2 rounded">{conv.response_text}</p>
                                            </div>
                                          </div>
                                          <div className="mt-2 text-xs text-gray-400">
                                            Tokens: {conv.tokens_used} | Week: {conv.week_number}
                                          </div>
                                        </CardContent>
                                      </Card>
                                    ))}
                                  </div>
                                </div>
                              )}
                            </TabsContent>
                            
                            <TabsContent value="info" className="mt-4">
                              <div className="space-y-4">
                                <div className="grid grid-cols-2 gap-4">
                                  <div>
                                    <Label className="text-gray-500">Student ID</Label>
                                    <p className="font-mono text-sm">{student.id}</p>
                                  </div>
                                  <div>
                                    <Label className="text-gray-500">Email</Label>
                                    <p>{student.email}</p>
                                  </div>
                                  <div>
                                    <Label className="text-gray-500">Weekly Quota</Label>
                                    <p>{student.current_week_quota.toLocaleString()}</p>
                                  </div>
                                  <div>
                                    <Label className="text-gray-500">Used Quota</Label>
                                    <p>{student.used_quota.toLocaleString()}</p>
                                  </div>
                                  <div>
                                    <Label className="text-gray-500">Created</Label>
                                    <p>{student.created_at ? new Date(student.created_at).toLocaleDateString() : 'N/A'}</p>
                                  </div>
                                </div>
                              </div>
                            </TabsContent>
                          </Tabs>
                        </DialogContent>
                      </Dialog>

                      <Button 
                        variant="ghost" 
                        size="icon"
                        onClick={() => regenerateMutation.mutate(student.id)}
                        title="Regenerate API Key"
                      >
                        <Key className="h-4 w-4" />
                      </Button>
                      <Button 
                        variant="ghost" 
                        size="icon"
                        onClick={() => studentsApi.resetQuota(student.id)}
                        title="Reset Quota"
                      >
                        <RotateCcw className="h-4 w-4" />
                      </Button>
                      <Button 
                        variant="ghost" 
                        size="icon"
                        onClick={() => deleteMutation.mutate(student.id)}
                        title="Delete"
                      >
                        <Trash2 className="h-4 w-4 text-red-500" />
                      </Button>
                    </div>
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
