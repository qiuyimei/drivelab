import {sqliteTable,text} from 'drizzle-orm/sqlite-core';
export const records=sqliteTable('records',{id:text('id').primaryKey(),owner:text('owner').notNull(),name:text('name').notNull(),scenario:text('scenario').notNull(),risk:text('risk').notNull(),created:text('created').notNull(),payload:text('payload').notNull()});
export const documents=sqliteTable('documents',{id:text('id').primaryKey(),owner:text('owner').notNull(),title:text('title').notNull(),body:text('body').notNull(),created:text('created').notNull(),metadata:text('metadata'),documentIndex:text('document_index')});
