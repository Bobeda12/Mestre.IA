import axios from 'axios';

// Fonte única da URL da API (Etapa 7) — antes disso, "http://127.0.0.1:8000"
// estava escrito à mão em 8 lugares (Home.tsx, CharacterCreation.tsx,
// GameChat.tsx), sem variável de ambiente nenhuma. Cai no valor de
// desenvolvimento se VITE_API_URL não estiver definido, pra não quebrar
// quem não configurou .env ainda.
export const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

export const api = axios.create({ baseURL: API_URL });
