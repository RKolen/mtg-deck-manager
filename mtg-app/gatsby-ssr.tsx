import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { GatsbySSR } from 'gatsby';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
    },
  },
});

export const wrapRootElement: GatsbySSR['wrapRootElement'] = ({ element }) => (
  <QueryClientProvider client={queryClient}>{element}</QueryClientProvider>
);
