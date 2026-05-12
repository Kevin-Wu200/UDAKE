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
  const response = await http.get<BackendResponse<TicketListData>>('/tickets', { params });
  const data = response.data.data;
  return {
    total: data.total,
    items: data.tickets
  };
}

export async function getTicket(ticketId: number): Promise<Ticket> {
  const response = await http.get<BackendResponse<{ ticket: Ticket }>>(`/tickets/${ticketId}`);
  return response.data.data.ticket;
}

export async function approveTicket(ticketId: number, notes: string): Promise<void> {
  await http.put(`/tickets/${ticketId}/approve`, { notes });
}

export async function rejectTicket(ticketId: number, reason: string): Promise<void> {
  await http.put(`/tickets/${ticketId}/reject`, { reason });
}
