import { http } from './http';
import type { Ticket, TicketListParams } from '../types/ticket';

interface BackendResponse<T> {
  success: boolean;
  message: string;
  data: T;
}

interface TicketListData {
  tickets: Ticket[];
  total: number;
}

export async function getTickets(params: TicketListParams): Promise<{ total: number; items: Ticket[] }> {
  const response = await http.get<BackendResponse<TicketListData>>('/api/tickets', { params });
  const data = response.data.data;
  return {
    total: data.total,
    items: data.tickets
  };
}

export async function getTicket(ticketId: number): Promise<Ticket> {
  const response = await http.get<BackendResponse<Ticket>>(`/api/tickets/${ticketId}`);
  return response.data.data;
}

export async function approveTicket(ticketId: number, notes: string): Promise<void> {
  await http.put(`/api/tickets/${ticketId}/approve`, { notes });
}

export async function rejectTicket(ticketId: number, reason: string): Promise<void> {
  await http.put(`/api/tickets/${ticketId}/reject`, { reason });
}
