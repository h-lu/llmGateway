import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { studentsApi } from '@/lib/api';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Plus, Key, RotateCcw, Trash2 } from 'lucide-react';
import type { Student } from '@/types';

export function StudentsPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');
  const [newStudent, setNewStudent] = useState({ name: '', email: '', quota: 10000 });
  const [createdKey, setCreatedKey] = useState<string | null>(null);

  const { data: students, isLoading } = useQuery({
    queryKey: ['students'],
    queryFn: studentsApi.list,
  });

  const createMutation = useMutation({
    mutationFn: studentsApi.create,
    onSuccess: (data) => {
      setCreatedKey(data.api_key);
      queryClient.invalidateQueries({ queryKey: ['students'] });
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

  if (isLoading) return <div>Loading...</div>;

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-3xl font-bold">Students</h2>
        <Dialog>
          <DialogTrigger asChild>
            <Button><Plus className="mr-2 h-4 w-4" /> Add Student</Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Create New Student</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div>
                <Label>Name</Label>
                <Input
                  value={newStudent.name}
                  onChange={e => setNewStudent({...newStudent, name: e.target.value})}
                />
              </div>
              <div>
                <Label>Email</Label>
                <Input
                  type="email"
                  value={newStudent.email}
                  onChange={e => setNewStudent({...newStudent, email: e.target.value})}
                />
              </div>
              <div>
                <Label>Weekly Quota</Label>
                <Input
                  type="number"
                  value={newStudent.quota}
                  onChange={e => setNewStudent({...newStudent, quota: parseInt(e.target.value)})}
                />
              </div>
              <Button
                onClick={() => createMutation.mutate(newStudent)}
                disabled={!newStudent.name || !newStudent.email}
              >
                Create
              </Button>
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

      <Input
        placeholder="Search students..."
        value={search}
        onChange={e => setSearch(e.target.value)}
        className="max-w-sm"
      />

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
