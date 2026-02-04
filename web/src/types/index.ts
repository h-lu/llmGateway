export interface Student {
  id: string;
  name: string;
  email: string;
  current_week_quota: number;
  used_quota: number;
  created_at: string;
  provider_type?: string;
}

export interface Conversation {
  id: number;
  student_id: string;
  timestamp: string;
  prompt_text: string;
  response_text: string;
  tokens_used: number;
  action_taken: string;
  rule_triggered?: string;
  week_number: number;
  model?: string;
}

export interface Rule {
  id: number;
  pattern: string;
  rule_type: 'block' | 'guide';
  message: string;
  active_weeks: string;
  enabled: boolean;
}

export interface WeeklyPrompt {
  id: number;
  week_start: number;
  week_end: number;
  system_prompt: string;
  description?: string;
  is_active: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface DashboardStats {
  students: number;
  conversations: number;
  conversations_today: number;
  rules: number;
  blocked: number;
  total_tokens: number;
  tokens_today: number;
  quota_usage_rate: number;
  current_week: number;
}
