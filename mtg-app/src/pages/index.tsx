import React from 'react';
import { graphql, type PageProps } from 'gatsby';

export const query = graphql`
  query HomePageQuery {
    allNodePage {
      nodes {
        drupalId
        title
        body {
          processed
        }
        path {
          alias
        }
      }
    }
  }
`;

interface PageNode {
  drupalId?: string | null;
  title: string;
  body?: { processed: string } | null;
  path?: { alias?: string | null } | null;
}

interface QueryData {
  allNodePage: {
    nodes: PageNode[];
  };
}

const IndexPage: React.FC<PageProps<QueryData>> = ({ data }) => {
  // Use the node whose path alias is "/" (the Drupal front page), falling
  // back to the first available page if no alias matches.
  const pages = data.allNodePage.nodes;
  const page =
    pages.find(n => n.path?.alias === '/') ?? pages[0] ?? null;

  return (
    <main style={{ padding: '1.5rem', maxWidth: 720 }}>
      {page != null ? (
        <>
          <h1>{page.title}</h1>
          {page.body != null && (
            <div
              // Body content is sanitised by Drupal before it reaches JSON:API.
              // eslint-disable-next-line react/no-danger
              dangerouslySetInnerHTML={{ __html: page.body.processed }}
            />
          )}
        </>
      ) : (
        <h1>MTG Deck Manager</h1>
      )}

      <nav style={{ marginTop: '1.5rem' }}>
        <ul style={{ listStyle: 'none', padding: 0, display: 'flex', gap: '1rem' }}>
          <li><a href="/collection">Collection</a></li>
          <li><a href="/decks">Decks</a></li>
          <li><a href="/import">Import XLSX</a></li>
        </ul>
      </nav>
    </main>
  );
};

export default IndexPage;
