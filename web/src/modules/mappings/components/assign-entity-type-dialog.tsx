import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Button } from "@/components/ui/button.js";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog.js";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form.js";
import { Input } from "@/components/ui/input.js";
import { useI18n } from "@/i18n/context.js";
import type { LocaleMessages } from "@/i18n/en.js";
import { OntologyUriPicker } from "@/modules/mappings/components/ontology-uri-picker.js";

type Copy = LocaleMessages["mappings"]["page"];

const schema = (subjectRequired: string, classRequired: string) =>
  z.object({
    subjectId: z.string().trim().min(1, subjectRequired),
    classUri: z.string().trim().min(1, classRequired),
  });

type Values = z.infer<ReturnType<typeof schema>>;

export function AssignEntityTypeDialog({
  open,
  onOpenChange,
  workspaceId,
  initialSubjectId,
  onSubmit,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  workspaceId: string;
  initialSubjectId?: string;
  onSubmit: (values: Values) => Promise<void>;
}) {
  const { t } = useI18n();
  const m = t.mappings.page;
  const formSchema = schema(m.validation_subject_required, m.validation_class_uri_required);
  const form = useForm<Values>({
    resolver: zodResolver(formSchema),
    defaultValues: { subjectId: "", classUri: "" },
  });

  useEffect(() => {
    if (!open) {
      form.reset({ subjectId: initialSubjectId ?? "", classUri: "" });
      return;
    }
    if (initialSubjectId) {
      form.setValue("subjectId", initialSubjectId);
    }
  }, [form, initialSubjectId, open]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="overflow-visible sm:max-w-lg" onOpenAutoFocus={(e) => e.preventDefault()}>
        <Form {...form}>
          <form
            className="grid gap-4"
            onSubmit={form.handleSubmit(async (values) => {
              await onSubmit(values);
              onOpenChange(false);
            })}
          >
            <DialogHeader>
              <DialogTitle>{m.assign_type_dialog_title}</DialogTitle>
              <DialogDescription>{m.assign_type_dialog_desc}</DialogDescription>
            </DialogHeader>
            <FormField
              control={form.control}
              name="subjectId"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{m.label_subject_id}</FormLabel>
                  <FormControl>
                    <Input {...field} placeholder={m.subject_id_placeholder} className="font-mono text-xs" />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="classUri"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{m.label_target_uri_class}</FormLabel>
                  <FormControl>
                    <OntologyUriPicker
                      workspaceId={workspaceId}
                      entityType="class"
                      value={field.value}
                      onValueChange={field.onChange}
                      placeholder={m.ontology_uri_picker_placeholder_class}
                      emptySearchLabel={m.ontology_uri_picker_empty}
                      hint={m.ontology_uri_picker_hint}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
                {t.core.common.cancel}
              </Button>
              <Button type="submit" disabled={form.formState.isSubmitting}>
                {form.formState.isSubmitting ? m.saving : m.assign_type_submit}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
