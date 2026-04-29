import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { GatsbyBrowser } from 'gatsby';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
    },
  },
});

export const wrapRootElement: GatsbyBrowser['wrapRootElement'] = ({
  element,
}) => (
  <QueryClientProvider client={queryClient}>{element}</QueryClientProvider>
);
