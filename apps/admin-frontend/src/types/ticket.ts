export interface Ticket {
  id: number;
  ticket_id: string;
  ticket_type: 'key_request' | 'key_extension';
  status: 'pending' | 'approved' | 'rejected' | 'completed';
  email: string;
  phone: string;
  industry: string;
  organization: string;
  usage_purpose: string;
  key_type: string;
  existing_key?: string | null;
  assigned_key?: string | null;
  approval_notes?: string | null;
  response_message?: string | null;
  processed_by?: string | null;
  processed_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface TicketListParams {
  page: number;
  page_size: number;
  status?: Ticket['status'];
  ticket_type?: Ticket['ticket_type'];
  search?: string;
}
