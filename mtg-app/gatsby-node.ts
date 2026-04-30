import type { GatsbyNode } from 'gatsby';

/**
 * Explicitly define NodePage so the home page query does not fail when no
 * basic_page nodes exist yet.
 */
export const createSchemaCustomization: GatsbyNode['createSchemaCustomization'] =
  ({ actions }) => {
    const { createTypes } = actions;

    createTypes(`
      type NodePageBodyField {
        processed: String
      }

      type NodePage implements Node {
        drupalId: String
        title: String
        body: NodePageBodyField
        path: NodePagePath
      }

      type NodePagePath {
        alias: String
      }
    `);
  };
