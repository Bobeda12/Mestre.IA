import axios from 'axios';

// Fonte única da URL da API (Etapa 7) — antes disso, "http://127.0.0.1:8000"
// estava escrito à mão em 8 lugares (Home.tsx, CharacterCreation.tsx,
// GameChat.tsx), sem variável de ambiente nenhuma. Cai no valor de
// desenvolvimento se VITE_API_URL não estiver definido, pra não quebrar
// quem não configurou .env ainda.
//
// "localhost", não "127.0.0.1": desde a Etapa 8, a sessão é um cookie
// SameSite=Lax. Pra fins de SameSite, "localhost" e "127.0.0.1" são sites
// DIFERENTES (o algoritmo trata hostname e literal de IP como sites
// distintos) — com o front em localhost:5173 e a API em 127.0.0.1:8000,
// o pedido vira cross-site e o navegador recusa devolver o cookie (mesmo
// content ele aceite receber o Set-Cookie). `curl` não pega isso porque
// não aplica SameSite — só apareceu testando no navegador de verdade.
export const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// Etapa 8 (ADR-0014): a sessão vive num cookie httpOnly, não mais em token
// no localStorage — `withCredentials` é o que faz o navegador mandar
// (e aceitar) esse cookie em pedidos cross-origin (front em :5173, back em
// :8000, mesmo site). O backend precisa de CORS com origem específica +
// credentials para isso funcionar (allow_origins=["*"] não é compatível
// com cookies).
export const api = axios.create({ baseURL: API_URL, withCredentials: true });
