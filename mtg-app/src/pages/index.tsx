import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { gql } from 'graphql-request';
import parse from 'html-react-parser';
import { getGraphQLClient } from '../services/graphqlClient';

interface PageNode {
  id: string;
  title: string;
  body?: string | null;
  pathAlias?: string | null;
}

async function fetchPages(): Promise<PageNode[]> {
  const data = await getGraphQLClient().request<{ pages: PageNode[] }>(gql`
    query { pages { id title body pathAlias } }
  `);
  return data.pages;
}

const IndexPage: React.FC = () => {
  const { data: pages = [] } = useQuery({ queryKey: ['pages'], queryFn: fetchPages });
  const page = pages.find(n => n.pathAlias === '/') ?? pages[0] ?? null;

  return (
    <main style={{ padding: '1.5rem', maxWidth: 720 }}>
      {page != null ? (
        <>
          <h1>{page.title}</h1>
          {page.body != null && <div>{parse(page.body)}</div>}
        </>
      ) : (
        <h1>MTG Deck Manager</h1>
      )}

      <nav style={{ marginTop: '1.5rem' }}>
        <ul style={{ listStyle: 'none', padding: 0, display: 'flex', gap: '1rem' }}>
          <li><a href="/collection">Collection</a></li>
          <li><a href="/decks">Decks</a></li>
          <li><a href="/import">Import XLSX</a></li>
          <li><a href="/meta-decks">Meta Decks</a></li>
        </ul>
      </nav>
    </main>
  );
};

export default IndexPage;
