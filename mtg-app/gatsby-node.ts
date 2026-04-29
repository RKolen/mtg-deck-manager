import type { GatsbyNode } from 'gatsby';

/**
 * Explicitly define the NodeMtgCard GraphQL type so the collection page
 * query does not fail when no cards have been imported yet (gatsby-source-drupal
 * only creates types when at least one record exists).
 */
export const createSchemaCustomization: GatsbyNode['createSchemaCustomization'] =
  ({ actions }) => {
    const { createTypes } = actions;

    createTypes(`
      type NodeMtgCard implements Node {
        drupalId: String
        title: String
        field_mana_cost: String
        field_cmc: Float
        field_type_line: String
        field_colors: [String]
        field_color_identity: [String]
        field_oracle_text: String
        field_scryfall_id: String
        field_image_uri: String
        field_is_mana_producer: Boolean
        field_produced_mana: [String]
        field_legal_formats: [String]
      }

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
