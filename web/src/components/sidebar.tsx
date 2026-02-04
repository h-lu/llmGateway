import { Link, useLocation } from 'react-router-dom';
import {
  LayoutDashboard, Users, MessageSquare, Shield,
  Calendar, Menu, X
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useState } from 'react';

const navItems = [
  { icon: LayoutDashboard, label: 'Dashboard', path: '/' },
  { icon: Users, label: 'Students', path: '/students' },
  { icon: MessageSquare, label: 'Conversations', path: '/conversations' },
  { icon: Shield, label: 'Rules', path: '/rules' },
  { icon: Calendar, label: 'Weekly Prompts', path: '/weekly-prompts' },
];

export function Sidebar() {
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);

  return (
    <aside className={`bg-slate-900 text-white transition-all ${collapsed ? 'w-16' : 'w-64'}`}>
      <div className="p-4 flex items-center justify-between">
        {!collapsed && <h1 className="text-xl font-bold">TeachProxy</h1>}
        <Button variant="ghost" size="icon" onClick={() => setCollapsed(!collapsed)} className="text-white hover:bg-slate-800">
          {collapsed ? <Menu size={20} /> : <X size={20} />}
        </Button>
      </div>

      <nav className="mt-8">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = location.pathname === item.path;

          return (
            <Link
              key={item.path}
              to={item.path}
              className={`flex items-center px-4 py-3 transition-colors ${
                isActive ? 'bg-slate-800 text-blue-400' : 'hover:bg-slate-800'
              }`}
            >
              <Icon size={20} />
              {!collapsed && <span className="ml-3">{item.label}</span>}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
