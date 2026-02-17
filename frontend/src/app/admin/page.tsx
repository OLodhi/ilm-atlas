"use client";

import { useCallback, useRef } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { UploadForm } from "@/components/admin/upload-form";
import { SourcesTable } from "@/components/admin/sources-table";
import { BooksTable } from "@/components/admin/books-table";

export default function AdminPage() {
  // Force sources table to re-fetch when upload completes
  const sourcesKeyRef = useRef(0);
  const handleUploaded = useCallback(() => {
    sourcesKeyRef.current += 1;
  }, []);

  return (
    <main className="mx-auto max-w-5xl p-6">
      <h1 className="mb-6 text-2xl font-semibold tracking-tight">
        Admin Panel
      </h1>
      <Tabs defaultValue="upload">
        <TabsList>
          <TabsTrigger value="upload">Upload</TabsTrigger>
          <TabsTrigger value="sources">Sources</TabsTrigger>
          <TabsTrigger value="books">Books</TabsTrigger>
        </TabsList>

        <TabsContent value="upload" className="mt-6">
          <UploadForm onUploaded={handleUploaded} />
        </TabsContent>

        <TabsContent value="sources" className="mt-6">
          <SourcesTable />
        </TabsContent>

        <TabsContent value="books" className="mt-6">
          <BooksTable />
        </TabsContent>
      </Tabs>
    </main>
  );
}
