export interface Ticket {
  id: number;
  type: 'key_request' | 'key_extension';
  status: 'pending' | 'approved' | 'rejected' | 'completed';
  applicant_email: string;
  applicant_phone?: string;
  industry?: string;
  purpose?: string;
  key_type?: string;
  existing_key_id?: number;
  assigned_key_id?: number;
  notes?: string;
  created_at: string;
  updated_at: string;
  processed_by?: string;
  processed_at?: string;
}

export interface TicketListParams {
  page: number;
  page_size: number;
  status?: Ticket['status'];
  ticket_type?: Ticket['type'];
  search?: string;
}
