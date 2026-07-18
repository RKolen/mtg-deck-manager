import type { AppProps } from 'next/app';
import Head from 'next/head';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useState } from 'react';
import { ThemeProvider } from '../context/ThemeContext';
import { AppShell } from '../components/design/AppShell';
import '../styles/tokens.css';

export default function App({ Component, pageProps }: AppProps) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30_000,
            retry: 1,
          },
        },
      }),
  );

  const deckTitle =
    typeof pageProps.deckTitle === 'string' ? pageProps.deckTitle : null;

  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <Head>
          <title>MTG // Deck Manager</title>
        </Head>
        <AppShell deckTitle={deckTitle}>
          <Component {...pageProps} />
        </AppShell>
      </ThemeProvider>
    </QueryClientProvider>
  );
}
