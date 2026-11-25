// Drizzle table definitions for the typed write paths. The DDL source of truth is migrations/0001_core.sql
// (RLS, triggers, views and functions are SQL Drizzle cannot express); these mirror its columns.
import { pgTable, uuid, text, timestamp, smallint, jsonb, bigint, date, numeric, boolean } from "drizzle-orm/pg-core";

export const huntItems = pgTable("hunt_items", {
  id: uuid("id").primaryKey(),
  workspaceId: uuid("workspace_id").notNull(),
  huntTypeId: uuid("hunt_type_id").notNull(),
  huntType: text("hunt_type").notNull(),
  externalId: text("external_id").notNull(),
  personId: uuid("person_id"),
  companyId: uuid("company_id"),
  target: text("target").notNull(),
  signal: text("signal").notNull(),
  signalAt: timestamp("signal_at", { withTimezone: true, mode: "string" }).notNull(),
  foundAt: timestamp("found_at", { withTimezone: true, mode: "string" }),
  fit: smallint("fit"),
  stage: text("stage"),
  vslStage: text("vsl_stage"),
  replyStatus: text("reply_status"),
  backendAgent: text("backend_agent"),
  frontendAgent: text("frontend_agent"),
  roostId: uuid("roost_id"),
  subtype: text("subtype"),
  oneShotSystem: text("one_shot_system"),
  details: jsonb("details"),
  createdBy: jsonb("created_by"),
  deletedAt: timestamp("deleted_at", { withTimezone: true, mode: "string" }),
});

export const fundingSignals = pgTable("funding_signals", {
  itemId: uuid("item_id").primaryKey(),
  workspaceId: uuid("workspace_id").notNull(),
  kind: text("kind").notNull(),
  round: text("round").notNull(),
  amountUsd: bigint("amount_usd", { mode: "number" }),
  announcedOn: date("announced_on", { mode: "string" }).notNull(),
  leadInvestor: text("lead_investor"),
  sourceUrl: text("source_url").notNull(),
});

export const jobPosts = pgTable("job_posts", {
  itemId: uuid("item_id").primaryKey(),
  workspaceId: uuid("workspace_id").notNull(),
  title: text("title").notNull(),
  board: text("board").notNull(),
  postedAt: timestamp("posted_at", { withTimezone: true, mode: "string" }).notNull(),
  location: text("location"),
  salaryRange: text("salary_range"),
  sourceUrl: text("source_url").notNull(),
});

export const upworkJobs = pgTable("upwork_jobs", {
  itemId: uuid("item_id").primaryKey(),
  workspaceId: uuid("workspace_id").notNull(),
  title: text("title").notNull(),
  budgetType: text("budget_type"),
  budgetMinUsd: numeric("budget_min_usd"),
  budgetMaxUsd: numeric("budget_max_usd"),
  clientCountry: text("client_country"),
  clientSpendUsd: numeric("client_spend_usd"),
  clientHireRate: numeric("client_hire_rate"),
  proposalsBand: text("proposals_band"),
  postedAt: timestamp("posted_at", { withTimezone: true, mode: "string" }).notNull(),
  jobUrl: text("job_url"),
});

export const investorSignals = pgTable("investor_signals", {
  itemId: uuid("item_id").primaryKey(),
  workspaceId: uuid("workspace_id").notNull(),
  investor: text("investor").notNull(),
  firm: text("firm"),
  investorKind: text("investor_kind").notNull(),
  lane: text("lane"),
  verified: boolean("verified"),
  dealCompany: text("deal_company"),
  dealRound: text("deal_round"),
  dealAmount: text("deal_amount"),
  dealDate: date("deal_date", { mode: "string" }),
  dealUrl: text("deal_url"),
  similarity: smallint("similarity"),
  checkMin: bigint("check_min", { mode: "number" }),
  checkMax: bigint("check_max", { mode: "number" }),
  coldRoute: text("cold_route"),
  thesisQuote: text("thesis_quote"),
  xHandle: text("x_handle"),
  portfolioUrl: text("portfolio_url"),
  score: smallint("score"),
  scoreParts: jsonb("score_parts"),
  sourceUrl: text("source_url").notNull(),
});
