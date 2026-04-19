import { defineStore } from 'pinia';
import { getTickets, getTicket, approveTicket, rejectTicket } from '../services/ticketApi';
import type { Ticket, TicketListParams } from '../types/ticket';

export const useTicketStore = defineStore('ticket', {
  state: () => ({
    tickets: [] as Ticket[],
    currentTicket: null as Ticket | null,
    total: 0,
    loading: false
  }),
  actions: {
    async fetchTickets(params: TicketListParams) {
      this.loading = true;
      try {
        const { total, items } = await getTickets(params);
        this.total = total;
        this.tickets = items;
      } finally {
        this.loading = false;
      }
    },
    async fetchTicketDetail(ticketId: number) {
      this.loading = true;
      try {
        this.currentTicket = await getTicket(ticketId);
      } finally {
        this.loading = false;
      }
    },
    async approve(ticketId: number, notes: string) {
      await approveTicket(ticketId, notes);
    },
    async reject(ticketId: number, reason: string) {
      await rejectTicket(ticketId, reason);
    }
  }
});
